from __future__ import annotations

import os
from pathlib import Path


def husk_home() -> Path:
    custom = os.environ.get("HUSK_HOME")
    base = Path(custom) if custom else Path.home() / ".husk"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_url() -> str:
    return f"sqlite+aiosqlite:///{husk_home() / 'traces.db'}"


def sync_db_url() -> str:
    return f"sqlite:///{husk_home() / 'traces.db'}"


def runs_dir() -> Path:
    d = husk_home() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def auth_file_path() -> Path:
    """Where the persisted session token + email lives on disk."""
    return husk_home() / "auth.json"


def cloud_url() -> str:
    """husk-cloud base URL. Override with HUSK_CLOUD_URL for dev or self-host."""
    return os.environ.get("HUSK_CLOUD_URL", "http://localhost:8080").rstrip("/")


def marketing_url() -> str:
    """Marketing site origin (where the user signs up + authorizes the CLI)."""
    return os.environ.get("HUSK_MARKETING_URL", "http://localhost:3000").rstrip("/")


def stub_auth() -> bool:
    """When true, accept any JWT shaped like husk-cloud's without verifying the signature.

    Convenient while Supabase isn't wired. Production should set HUSK_STUB_AUTH=0.
    """
    return os.environ.get("HUSK_STUB_AUTH", "1") != "0"
