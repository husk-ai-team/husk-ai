"""Local, gitignored storage for the debugger's BYOK config + API keys.

The key stays on the user's machine in ``~/.husk/secrets.json`` (the same dir as
the existing ``auth.json``; ``~/.husk`` is outside the repo, so it is never
committed). On POSIX the file is chmod 0600. An environment variable
(``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``) is honored as a fallback so a key
already in the shell works without re-entry.

Hard rules enforced here:
  * the key is NEVER logged (this module logs nothing containing a key);
  * :func:`public_config` NEVER returns the key — only ``has_key: bool``;
  * the key is NEVER written anywhere but ``secrets.json``.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from typing import Any

from husk_studio_backend.config import husk_home

log = logging.getLogger(__name__)

# provider name -> environment variable consulted as a fallback key source.
PROVIDER_ENV_VAR: dict[str, str] = {
    "regolo": "REGOLO_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

# Regolo.ai is the default: EU-hosted, GDPR, zero data-retention — so a non-tech
# team's run data leaves for analysis only to an EU provider. Anthropic / OpenAI /
# OpenRouter stay selectable in Settings.
DEFAULT_PROVIDER = "regolo"
DEFAULT_MODEL = "Llama-3.3-70B-Instruct"

_PUBLIC_FIELDS = ("provider", "model", "auto_analyze")


def _secrets_path() -> Any:
    return husk_home() / "secrets.json"


def _default_config() -> dict[str, Any]:
    return {
        "provider": DEFAULT_PROVIDER,
        "model": DEFAULT_MODEL,
        "auto_analyze": False,
        "keys": {},  # provider -> api key (local only)
    }


def _load_raw() -> dict[str, Any]:
    path = _secrets_path()
    if not path.exists():
        return _default_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupt/unreadable file: fall back to defaults rather than crash. Do
        # NOT log the contents (it may contain a key).
        log.warning("debugger secrets file unreadable; using defaults")
        return _default_config()
    base = _default_config()
    if isinstance(data, dict):
        base.update({k: data[k] for k in data if k != "keys"})
        keys = data.get("keys")
        if isinstance(keys, dict):
            base["keys"] = {str(k): str(v) for k, v in keys.items() if v}
    return base


def _write_raw(config: dict[str, Any]) -> None:
    path = _secrets_path()
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    # Best-effort lock-down on POSIX; a no-op / harmless on Windows.
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


def public_config() -> dict[str, Any]:
    """Config safe to send to the UI: never includes the key."""
    raw = _load_raw()
    provider = str(raw.get("provider") or DEFAULT_PROVIDER)
    return {
        "provider": provider,
        "model": str(raw.get("model") or DEFAULT_MODEL),
        "auto_analyze": bool(raw.get("auto_analyze")),
        "has_key": resolve_api_key(provider) is not None,
    }


def save_config(
    *,
    provider: str | None = None,
    model: str | None = None,
    auto_analyze: bool | None = None,
    api_key: str | None = None,
) -> None:
    """Persist config. A provided ``api_key`` is stored for the active provider.

    Omitted fields keep their current value; an omitted ``api_key`` preserves the
    existing key (it is never cleared by a config save that doesn't mention it).
    """
    cfg = _load_raw()
    if provider is not None:
        cfg["provider"] = provider
    if model is not None:
        cfg["model"] = model
    if auto_analyze is not None:
        cfg["auto_analyze"] = bool(auto_analyze)
    if api_key:
        target = provider or cfg.get("provider") or DEFAULT_PROVIDER
        keys = dict(cfg.get("keys") or {})
        keys[target] = api_key
        cfg["keys"] = keys
    _write_raw(cfg)


def clear_key(provider: str) -> None:
    """Remove a stored key for ``provider`` (does not touch env vars)."""
    cfg = _load_raw()
    keys = dict(cfg.get("keys") or {})
    keys.pop(provider, None)
    cfg["keys"] = keys
    _write_raw(cfg)


def resolve_api_key(provider: str) -> str | None:
    """The key for ``provider``: stored key first, then env var fallback.

    Returns ``None`` when no key is available. Never logs the key.
    """
    cfg = _load_raw()
    stored = (cfg.get("keys") or {}).get(provider)
    if stored:
        return str(stored)
    env_var = PROVIDER_ENV_VAR.get(provider)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    return None
