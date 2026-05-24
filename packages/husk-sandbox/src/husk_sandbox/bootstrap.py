from __future__ import annotations

import logging
import runpy
import sys
import traceback
from pathlib import Path

from husk_sandbox.tracer import emitter_from_env

log = logging.getLogger(__name__)


def _install_integrations() -> None:
    """Lazy-install framework integrations that are importable.

    Each integration registers itself as a global callback handler so the user's
    agent script can be imported as-is without code changes.
    """
    try:
        from husk_sandbox.integrations import langchain as lc

        lc.install()
    except ImportError:
        log.debug("LangChain integration not installed (langchain not importable).")

    try:
        from husk_sandbox.integrations import langgraph as lg

        lg.install()
    except ImportError:
        log.debug("LangGraph integration not installed (langgraph not importable).")


def main(argv: list[str] | None = None) -> int:
    """Entry point: `python -m husk_sandbox.bootstrap <script.py> [args...]`."""
    argv = argv or sys.argv[1:]
    if not argv:
        log.error("husk_sandbox.bootstrap: missing script argument")
        return 2

    script = Path(argv[0]).resolve()
    script_args = argv[1:]

    emitter = emitter_from_env()
    if emitter is None:
        # Running standalone without Husk env vars — execute script as a no-op passthrough.
        log.warning("HUSK_RUN_ID/HUSK_EVENT_PIPE not set; running without tracing.")

    _install_integrations()

    sys.argv = [str(script), *script_args]
    sys.path.insert(0, str(script.parent))

    status = "success"
    error: str | None = None
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:  # noqa: PERF203
        if e.code not in (None, 0):
            status = "error"
            error = f"SystemExit({e.code})"
    except BaseException as e:  # noqa: BLE001
        status = "error"
        error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        if emitter:
            emitter.close(status=status, error=error)
        raise
    finally:
        if emitter:
            emitter.close(status=status, error=error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
