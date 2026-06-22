"""Tests for the husk run / replay / export CLI commands (added with the features)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    return tmp_path


def test_run_injects_otel_env_and_runs_command(monkeypatch: pytest.MonkeyPatch) -> None:
    import husk.cli as cli

    # Pretend the backend is already up so `run` doesn't try to boot one.
    monkeypatch.setattr(cli, "_backend_healthy", lambda base: True)

    captured: dict[str, object] = {}

    class _FakeProc:
        returncode = 0

    def _fake_run(cmd: list[str], env: dict[str, str] | None = None) -> _FakeProc:
        captured["cmd"] = cmd
        captured["env"] = env
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    res = CliRunner().invoke(cli.main, ["run", "--port", "7654", "echo", "hi"])
    assert res.exit_code == 0, res.output
    assert captured["cmd"] == ["echo", "hi"]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://127.0.0.1:7654"
    assert "127.0.0.1:7654/runs" in res.output


def test_replay_posts_expected_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    import husk.cli as cli

    captured: dict[str, object] = {}

    class _FakeResp:
        status_code = 200
        text = ""

        def json(self) -> dict[str, str]:
            return {"thread_id": "t", "child_id": "c"}

    def _fake_post(url: str, json: dict | None = None, timeout: float | None = None) -> _FakeResp:
        captured["url"] = url
        captured["body"] = json
        return _FakeResp()

    monkeypatch.setattr(httpx, "post", _fake_post)

    res = CliRunner().invoke(
        cli.main,
        ["replay", "run1", "--set", "topic=Tokyo", "--set", "n=3", "--cassette"],
    )
    assert res.exit_code == 0, res.output
    assert str(captured["url"]).endswith("/api/replay")
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["run_id"] == "run1"
    # "Tokyo" isn't valid JSON -> kept as string; "3" parses as int.
    assert body["state_override"] == {"topic": "Tokyo", "n": 3}
    assert body["use_cassette"] is True


def test_export_bundles_run_spans_branches(isolated_home: Path) -> None:
    from husk_studio_backend.db.engine import sync_engine, sync_session
    from husk_studio_backend.db.models import Base, RunRow, SpanRow

    # Create the schema on the (global) sync engine and seed one run + span.
    Base.metadata.create_all(sync_engine())
    with sync_session() as s:
        s.add(
            RunRow(
                id="exp_run_1",
                script_path="agent.py",
                framework="otel/openai",
                status="success",
                started_at=1,
                finished_at=2,
            )
        )
        s.add(
            SpanRow(
                id="exp_span_1",
                run_id="exp_run_1",
                kind="llm",
                name="chat",
                started_at=1,
                finished_at=2,
                status="success",
                input_inline={"messages": [{"role": "user", "content": "hi"}]},
            )
        )
        s.commit()

    import husk.cli as cli

    res = CliRunner().invoke(cli.main, ["export", "exp_run_1"])
    assert res.exit_code == 0, res.output
    bundle = json.loads(res.output)
    assert bundle["husk_export_version"] == 1
    assert bundle["run"]["id"] == "exp_run_1"
    assert len(bundle["spans"]) == 1
    assert bundle["spans"][0]["id"] == "exp_span_1"
    assert "branches" in bundle


def test_export_unknown_run_errors() -> None:
    import husk.cli as cli

    res = CliRunner().invoke(cli.main, ["export", "does-not-exist"])
    assert res.exit_code == 1
    assert "not found" in res.output.lower()
