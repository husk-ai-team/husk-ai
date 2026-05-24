from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from ulid import ULID

from husk.config import husk_home
from husk.ui_launcher import open_browser_at, start_studio_dev

log = logging.getLogger(__name__)


def _start_backend(port: int, run_id: str) -> threading.Thread:
    """Start FastAPI backend in a daemon thread via uvicorn programmatic API."""
    import uvicorn

    from husk_studio_backend.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True, name=f"husk-backend-{run_id}")
    t.start()
    # Wait for socket to be reachable (short busy wait, bounded).
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.02)
    return t


def _spawn_sandbox(
    script: Path,
    script_args: list[str],
    run_id: str,
    event_pipe_path: Path,
) -> subprocess.Popen[bytes]:
    """Spawn the sandbox subprocess that exec()s the user agent under instrumentation."""
    env = os.environ.copy()
    env["HUSK_RUN_ID"] = run_id
    env["HUSK_EVENT_PIPE"] = str(event_pipe_path)
    env["HUSK_HOME"] = str(husk_home())
    return subprocess.Popen(
        [sys.executable, "-m", "husk_sandbox.bootstrap", str(script), *script_args],
        env=env,
    )


def run_agent(
    *,
    script: Path,
    script_args: list[str],
    backend_port: int,
    studio_port: int,
    open_browser: bool,
    timeout: int | None,
) -> int:
    """Orchestrate a single `husk run` invocation.

    Returns the exit code of the sandbox subprocess.
    """
    run_id = str(ULID())
    log.info("Run id: %s", run_id)

    # Event channel: cross-OS we use a regular file in run_dir that the backend tails.
    from husk.config import run_dir

    rd = run_dir(run_id)
    event_path = rd / "events.jsonl"
    event_path.touch()

    log.info("Starting Studio backend on http://127.0.0.1:%d", backend_port)
    _start_backend(backend_port, run_id)

    studio_proc: subprocess.Popen[bytes] | None = None
    if open_browser:
        # In dev we expect Next.js running on studio_port. In packaged builds the backend
        # serves the static studio bundle itself (M3).
        studio_proc = start_studio_dev(studio_port)
        open_browser_at(f"http://localhost:{studio_port}/runs/{run_id}")

    log.info("Spawning sandbox for %s", script)
    proc = _spawn_sandbox(script, script_args, run_id, event_path)

    try:
        exit_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("Run timed out after %ds; terminating", timeout)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        exit_code = 124
    finally:
        if studio_proc is not None:
            studio_proc.terminate()

    log.info("Run %s finished with exit code %d", run_id, exit_code)
    return exit_code
