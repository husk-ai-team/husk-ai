"""A single local-only guard for state-changing / sensitive routes.

Husk is a loopback dev tool with no real authentication, yet some routes execute
user code (replay), write to disk (debugger apply-fix), or ingest spans that feed
those. Without a gate, any process on the box — or a web page the user is viewing,
via DNS-rebinding to 127.0.0.1 — could drive them. This dependency is the gate:

  * reject any request whose peer is not loopback (covers `--host 0.0.0.0`);
  * if an ``Origin`` header is present (i.e. a browser made the request), require
    its host to be loopback too. A DNS-rebinding page keeps its *document* origin
    (the attacker domain) in ``Origin``, so a loopback-host check rejects it while
    still allowing the Studio (served from localhost on any port).

Non-browser clients (the OTel exporter, the MCP server, curl) send no ``Origin``
and connect from loopback, so they pass unchanged.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from fastapi import status as _status
from fastapi.exceptions import HTTPException

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_loopback(host: str | None) -> bool:
    return bool(host) and host in _LOOPBACK_HOSTS


async def local_only(request: Request) -> None:
    """FastAPI dependency: allow only loopback, same-host requests."""
    client_host = request.client.host if request.client else None
    if not _is_loopback(client_host):
        raise HTTPException(
            status_code=_status.HTTP_403_FORBIDDEN,
            detail="local-only endpoint: non-loopback client refused",
        )
    origin = request.headers.get("origin")
    if origin:
        if not _is_loopback(urlparse(origin).hostname):
            raise HTTPException(
                status_code=_status.HTTP_403_FORBIDDEN,
                detail="cross-origin request refused",
            )
