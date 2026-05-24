"""Local-side auth endpoints used by the studio.

Flow (browser OAuth-style):

  1. Studio (no session) → POST /api/auth/start
     - we generate a `state` nonce, remember it for ~5 min, return
       `{state, authorize_url}` pointing to `<marketing>/auth/cli?cb=...&state=...`.
  2. Studio opens that URL in the browser. User signs in / signs up on the
     marketing site, then clicks "Allow" on the CLI authorize page.
  3. Marketing site POSTs `{code, state}` to /api/auth/cli-callback.
  4. We verify the `state`, exchange the code with husk-cloud, persist the
     issued JWT to ~/.husk/auth.json, and return 204.
  5. Studio polls GET /api/auth/me; once it sees the token, navigates inside.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from husk_studio_backend.config import (
    auth_file_path,
    cloud_url,
    marketing_url,
    stub_auth,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory state registry: state -> (created_at_ms, asyncio.Event signalled
# when the callback for that state lands so a polling /me can return faster).
_pending_states: dict[str, tuple[int, asyncio.Event]] = {}
_STATE_TTL_MS = 5 * 60_000


def _gc_states() -> None:
    now = int(time.time() * 1000)
    expired = [s for s, (t, _) in _pending_states.items() if now - t > _STATE_TTL_MS]
    for s in expired:
        _pending_states.pop(s, None)


class StartOut(BaseModel):
    state: str
    authorize_url: str


@router.post("/start", response_model=StartOut)
async def start_auth(request: Request) -> StartOut:
    """Begin the browser sign-in flow.

    Generates a random `state`, records it, returns the authorize URL the
    studio should open. The callback URL is built off the host:port this very
    request reached us on, so it works regardless of whether the backend
    landed on 7654 or fell back to 7655.
    """
    _gc_states()
    state = secrets.token_urlsafe(24)
    _pending_states[state] = (int(time.time() * 1000), asyncio.Event())
    # Use the same host:port the studio is using to talk to us. Falls back to
    # localhost:7654 for misconfigured proxies.
    host = request.url.hostname or "localhost"
    port = request.url.port or 7654
    callback = f"http://{host}:{port}/api/auth/cli-callback"
    params = urlencode({"cb": callback, "state": state})
    return StartOut(
        state=state,
        authorize_url=f"{marketing_url()}/auth/cli?{params}",
    )


class CallbackIn(BaseModel):
    code: str
    state: str


@router.post("/cli-callback", status_code=204)
async def cli_callback(req: CallbackIn) -> None:
    _gc_states()
    pending = _pending_states.pop(req.state, None)
    if pending is None:
        raise HTTPException(status_code=400, detail="unknown_or_expired_state")

    # Exchange the code with husk-cloud for a long-lived JWT.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{cloud_url()}/api/auth/cli-exchange",
                json={"code": req.code, "state": req.state},
            )
            if r.status_code != 200:
                detail = r.text[:200]
                raise HTTPException(status_code=502, detail=f"cloud_exchange_failed: {detail}")
            body = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"cloud_unreachable: {e}") from e

    payload = {
        "token": body["token"],
        "email": body.get("email", ""),
        "name": body.get("name", ""),
        "plan": body.get("plan", "free"),
        "saved_at": int(time.time() * 1000),
    }
    auth_file_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Saved CLI session for %s", payload["email"])

    # Signal any /me poll waiting on this state.
    _, evt = pending
    evt.set()


class MeOut(BaseModel):
    email: str
    name: str
    plan: str
    saved_at: int
    expires_at: int | None = None
    is_guest: bool = False


@router.get("/me", response_model=MeOut)
async def get_me() -> MeOut:
    path = auth_file_path()
    if not path.exists():
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="invalid_session_file") from None

    token = data.get("token", "")
    is_guest = bool(data.get("is_guest", False))
    # Validate the JWT shape; in stub mode we don't verify signature.
    try:
        claims = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": True},
            issuer="husk-cloud",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"token_invalid: {e}") from e

    # Guest sessions are local-only — husk-cloud has no record of them and
    # would 401 on verify. Skip the round-trip entirely.
    if not stub_auth() and not is_guest:
        # Production path: call husk-cloud to verify the license is still valid.
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(
                    f"{cloud_url()}/api/license/verify",
                    headers={"authorization": f"Bearer {token}"},
                )
                if r.status_code != 200:
                    raise HTTPException(status_code=401, detail="license_invalid")
        except httpx.HTTPError as e:
            # Network error → fall through with local claims; the user can keep
            # using the local product while offline (best-effort).
            log.warning("license verify offline: %s", e)

    return MeOut(
        email=data.get("email", claims.get("email", "")),
        name=data.get("name", ""),
        plan=data.get("plan", claims.get("plan", "free")),
        saved_at=int(data.get("saved_at", 0)),
        expires_at=int(claims.get("exp", 0)) if "exp" in claims else None,
        is_guest=is_guest,
    )


@router.post("/anonymous", status_code=204)
async def anonymous_session() -> None:
    """Create a guest session — no signup, no cloud round-trip.

    Husk is free for everyone. Hitting this endpoint writes a local-only
    JWT-shaped session to ~/.husk/auth.json so the studio behaves the same
    way as for a signed-in user, except `is_guest=True`. The token isn't
    known to husk-cloud; that's fine, because /api/auth/me skips the cloud
    verify when is_guest is set.
    """
    now = int(time.time())
    claims = {
        "sub": "guest",
        "email": "guest@husk.local",
        "plan": "free",
        "name": "Guest",
        "iat": now,
        "exp": now + 90 * 24 * 3600,
        "iss": "husk-cloud",
    }
    # Sign with a throwaway secret — /api/auth/me decodes with
    # verify_signature=False, and husk-cloud never sees this token.
    token = jwt.encode(claims, secrets.token_hex(16), algorithm="HS256")
    payload = {
        "token": token,
        "email": claims["email"],
        "name": claims["name"],
        "plan": claims["plan"],
        "saved_at": int(time.time() * 1000),
        "is_guest": True,
    }
    auth_file_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Created guest session at %s", auth_file_path())


@router.post("/logout", status_code=204)
async def logout() -> None:
    path = auth_file_path()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
