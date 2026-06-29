from __future__ import annotations

import os
from pathlib import Path


def husk_home() -> Path:
    custom = os.environ.get("HUSK_HOME")
    base = Path(custom) if custom else Path.home() / ".husk"
    existed = base.exists()
    base.mkdir(parents=True, exist_ok=True)
    if not existed:
        # The dir holds cleartext traces + the BYOK key. Restrict to the owner on
        # creation. POSIX: 0700. On Windows os.chmod can't express this, but the
        # user-profile ACL already restricts cross-user reads; this is best-effort.
        try:
            os.chmod(base, 0o700)
        except OSError:
            pass
    return base


def db_url() -> str:
    # HUSK_DB_URL can point the async engine at another SQLite path; the default —
    # local SQLite under ~/.husk — is the right store for a single-user dev debugger
    # (this process is the only writer).
    override = os.environ.get("HUSK_DB_URL")
    if override:
        return override
    return f"sqlite+aiosqlite:///{husk_home() / 'traces.db'}"


def sync_db_url() -> str:
    override = os.environ.get("HUSK_DB_URL_SYNC")
    if override:
        return override
    return f"sqlite:///{husk_home() / 'traces.db'}"


def runs_dir() -> Path:
    d = husk_home() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d
