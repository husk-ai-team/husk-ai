from __future__ import annotations

import logging
import os
import subprocess
import webbrowser

log = logging.getLogger(__name__)


def open_browser_at(url: str) -> None:
    """Open the default browser at the given URL, unless HUSK_NO_BROWSER is set."""
    if os.environ.get("HUSK_NO_BROWSER"):
        log.info("HUSK_NO_BROWSER set; would have opened %s", url)
        return
    try:
        webbrowser.open(url)
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to open browser at %s: %s", url, e)


def start_studio_dev(port: int) -> subprocess.Popen[bytes] | None:
    """Start the Next.js Studio dev server if available. No-op when in packaged mode.

    For M1 we assume the developer runs `pnpm --filter studio dev` themselves;
    this function returns None and is wired in M2/M3 for embedded bundle.
    """
    log.debug("start_studio_dev(%d) — no-op (run `pnpm --filter studio dev` manually).", port)
    return None


def open_studio(run_id: str, *, port: int, open_browser: bool) -> None:
    if open_browser:
        open_browser_at(f"http://localhost:{port}/runs/{run_id}")
