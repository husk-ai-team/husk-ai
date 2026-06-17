"""BYOK secrets: stored locally, never echoed, env fallback honored."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fresh_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


def test_public_config_never_returns_key(fresh_home: Path) -> None:
    from husk_studio_backend.debugger import secrets

    secrets.save_config(provider="anthropic", model="claude-sonnet-4", api_key="sk-xyz")
    cfg = secrets.public_config()

    assert cfg["has_key"] is True
    assert cfg["provider"] == "anthropic"
    assert "keys" not in cfg
    assert "sk-xyz" not in json.dumps(cfg)


def test_key_persists_only_in_secrets_file(fresh_home: Path) -> None:
    from husk_studio_backend.debugger import secrets

    secrets.save_config(provider="anthropic", model="claude-sonnet-4", api_key="sk-abc")
    assert secrets.resolve_api_key("anthropic") == "sk-abc"

    # The key lives in ~/.husk/secrets.json and nowhere else we expose.
    raw = json.loads((fresh_home / "secrets.json").read_text(encoding="utf-8"))
    assert raw["keys"]["anthropic"] == "sk-abc"


def test_env_var_fallback(fresh_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from husk_studio_backend.debugger import secrets

    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    assert secrets.resolve_api_key("openai") == "env-openai"
    # No stored key + no env var -> None.
    assert secrets.resolve_api_key("anthropic") is None


def test_saving_config_preserves_existing_key(fresh_home: Path) -> None:
    from husk_studio_backend.debugger import secrets

    secrets.save_config(provider="anthropic", model="claude-sonnet-4", api_key="sk-keep")
    # A later save that toggles a flag must not wipe the key.
    secrets.save_config(auto_analyze=True)
    assert secrets.resolve_api_key("anthropic") == "sk-keep"
    assert secrets.public_config()["auto_analyze"] is True
