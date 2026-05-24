from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from husk_studio_backend import __version__
from husk_studio_backend.api import (
    auth,
    branches,
    cursor,
    dashboard,
    diff,
    integrations,
    otel,
    runs,
    spans,
)
from husk_studio_backend.api import (
    langgraph as langgraph_api,
)
from husk_studio_backend.config import runs_dir
from husk_studio_backend.db.engine import init_db
from husk_studio_backend.ingest.jsonl_reader import discover_and_tail_active_runs

log = logging.getLogger(__name__)


def _find_studio_dist() -> Path | None:
    """Locate the bundled studio (apps/studio/dist) for production serving.

    Two search paths, in order:
      1. Inside the installed wheel: husk_studio_backend/studio_static/
         (populated at wheel-build time by `scripts/bundle_studio.py`).
      2. Relative to the workspace checkout: ../../../apps/studio/dist
         (used when running from a `uv sync` clone without a wheel).
    Returns the first path that has index.html, or None.
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here / "studio_static",
        here.parents[3] / "apps" / "studio" / "dist",
    ]
    for cand in candidates:
        if (cand / "index.html").is_file():
            return cand
    return None


def _ensure_studio_built() -> None:
    """Build the studio bundle if running from a workspace checkout without one.

    Idempotent. Skipped when:
      * Bundle already exists (wheel install OR previous build).
      * HUSK_NO_AUTO_BUILD=1 (tests, CI, devs who want to debug the fallback).
      * Not a workspace checkout (no apps/studio/package.json).
      * `corepack` not on PATH (no Node — user sees the landing page with
        instructions instead).
    Falls back to the landing HTML on subprocess failure (e.g. missing
    node_modules, vite crash, timeout).
    """
    if os.environ.get("HUSK_NO_AUTO_BUILD") == "1":
        return
    if _find_studio_dist() is not None:
        return

    here = Path(__file__).resolve().parent
    workspace_root = here.parents[3]
    studio_pkg = workspace_root / "apps" / "studio" / "package.json"
    if not studio_pkg.is_file():
        return  # wheel install or otherwise outside the workspace

    # shutil.which handles Windows PATHEXT (resolves to corepack.cmd) so we
    # don't need shell=True and the brittle quoting that comes with it.
    corepack = shutil.which("corepack")
    if corepack is None:
        log.warning(
            "Studio bundle not found and `corepack` is not on PATH. "
            "Serving the landing page. Install Node 20+ then run "
            "`corepack pnpm --filter studio build` to bake the bundle."
        )
        return

    log.info(
        "Studio bundle not found; building via `corepack pnpm --filter "
        "studio build` (~10-30s on first run; subsequent boots are instant)..."
    )
    try:
        subprocess.run(
            [corepack, "pnpm", "--filter", "studio", "build"],
            cwd=workspace_root,
            check=True,
            timeout=180,
        )
        log.info("Studio bundle built.")
    except subprocess.CalledProcessError as exc:
        log.warning(
            "Studio auto-build failed (exit %d). Serving landing page. "
            "Likely cause: missing node_modules. From the repo root run "
            "`corepack pnpm install && corepack pnpm --filter studio build` "
            "then restart `husk-ai start`.",
            exc.returncode,
        )
    except subprocess.TimeoutExpired:
        log.warning(
            "Studio auto-build timed out after 180s. Serving landing page. "
            "Run `corepack pnpm --filter studio build` manually."
        )
    except OSError as exc:
        log.warning("Studio auto-build OS error: %s. Serving landing page.", exc)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    # Pick up any legacy JSONL runs left over from earlier sandbox sessions.
    asyncio.create_task(discover_and_tail_active_runs(runs_dir()))
    yield


app = FastAPI(
    title="Husk Studio Backend",
    version=__version__,
    description="Local API + WebSocket for the Husk visual debugger.",
    lifespan=lifespan,
)

# The Studio (Vite) runs at :5174 in dev; the Marketing site at :3000 (or :5173).
# In a packaged build the backend itself serves the Studio bundle from `/` (Day 7).
app.add_middleware(
    CORSMiddleware,
    # The marketing site (husk.dev in prod, localhost:3000 in dev) POSTs
    # cross-origin to /api/auth/cli-callback during the CLI sign-in flow, so
    # we have to allow both the public origin and the dev origins.
    allow_origins=[
        "https://husk.dev",
        "https://www.husk.dev",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(runs.router)
app.include_router(spans.router)
app.include_router(branches.router)
app.include_router(diff.router)
app.include_router(otel.router)
app.include_router(cursor.router)
app.include_router(langgraph_api.router)
app.include_router(integrations.router)
app.include_router(dashboard.router)
app.include_router(auth.router)


_LANDING_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Husk - Studio not built yet</title>
    <style>
      :root { color-scheme: dark; }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif;
        background: #0F1117;
        color: #E6E6E6;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 2rem;
        line-height: 1.55;
      }
      .wrap { max-width: 720px; width: 100%; }
      h1 {
        margin: 0 0 0.5rem;
        font-size: 1.875rem;
        letter-spacing: -0.02em;
        font-weight: 700;
      }
      .accent { color: #FF6B35; }
      .lead { color: #8B949E; margin: 0 0 2rem; font-size: 1rem; }
      .grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 1rem;
      }
      @media (min-width: 720px) {
        .grid { grid-template-columns: 1fr 1fr; }
      }
      .card {
        border: 1px solid #30363D;
        background: #161B22;
        padding: 1.5rem;
        border-radius: 12px;
        transition: border-color .2s;
      }
      .card:hover { border-color: rgba(255, 107, 53, 0.5); }
      .card h2 {
        margin: 0 0 0.25rem;
        font-size: 1.125rem;
        font-weight: 600;
      }
      .card .sub {
        margin: 0 0 1rem;
        font-size: 0.8125rem;
        color: #8B949E;
      }
      .eyebrow {
        font-size: 0.6875rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: #FF6B35;
        font-weight: 600;
        margin: 0 0 0.5rem;
      }
      code, pre {
        font-family: "Geist Mono", "JetBrains Mono", "Courier New", monospace;
        font-size: 0.8125rem;
      }
      pre {
        background: #0D1117;
        border: 1px solid #21262D;
        border-radius: 6px;
        padding: 0.625rem 0.75rem;
        margin: 0.375rem 0;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-word;
      }
      pre .prompt { color: #FF6B35; user-select: none; }
      .footer {
        margin-top: 2rem;
        padding-top: 1.25rem;
        border-top: 1px solid #21262D;
        font-size: 0.8125rem;
        color: #6B7280;
      }
      a { color: #FF6B35; text-decoration: none; }
      a:hover { text-decoration: underline; }
      .why {
        margin-top: 1.25rem;
        padding: 0.875rem 1rem;
        border-radius: 8px;
        background: rgba(255, 107, 53, 0.05);
        border: 1px solid rgba(255, 107, 53, 0.2);
        font-size: 0.8125rem;
        color: #B8B8B8;
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <p class="eyebrow">Backend is running on port __PORT__</p>
      <h1>Husk <span class="accent">Studio</span> isn't built yet.</h1>
      <p class="lead">
        The API is live but the UI bundle is missing. Pick one of the two options below.
      </p>

      <div class="grid">
        <div class="card">
          <p class="eyebrow">Option 1</p>
          <h2>Build the bundle once</h2>
          <p class="sub">Permanent. Studio loads from <code>/</code> after this.</p>
          <pre><span class="prompt">$ </span>corepack pnpm install</pre>
          <pre><span class="prompt">$ </span>corepack pnpm --filter studio build</pre>
          <p class="sub" style="margin-top:0.75rem">
            Then <a href="/">reload this page</a>.
          </p>
        </div>

        <div class="card">
          <p class="eyebrow">Option 2</p>
          <h2>Dev server (hot reload)</h2>
          <p class="sub">For editing Studio source. Vite at <code>:5174</code>, proxies <code>/api</code> back here.</p>
          <pre><span class="prompt">$ </span>corepack pnpm dev:studio</pre>
          <p class="sub" style="margin-top:0.75rem">
            Then open <a href="http://localhost:5174">http://localhost:5174</a>.
          </p>
        </div>
      </div>

      <div class="why">
        <strong style="color:#FF6B35">Why am I seeing this page?</strong>
        Either (a) you cloned the repo and haven't built the Studio yet, OR
        (b) auto-build tried and failed (check the terminal where you ran
        <code>husk-ai start</code> for the warning). Both options above need
        Node.js 20+ and <code>corepack</code> enabled. See the
        <a href="https://husk.dev/get-started#studio-development">full guide</a>.
      </div>

      <p class="footer">
        API health: <a href="/api/health">/api/health</a>
        &nbsp;&middot;&nbsp; Backend version: __VERSION__
        &nbsp;&middot;&nbsp; Need Node?
        <a href="https://husk.dev/get-started#step-4">install guide</a>
      </p>
    </div>
  </body>
</html>
"""


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "husk-studio-backend", "version": __version__}


@app.get("/healthz")
async def healthz() -> dict:
    # Back-compat alias for older clients.
    return {"ok": True}


# Mount the bundled studio at /. If we're in a workspace checkout without a
# dist/, try to build it once before falling back to the landing page (no-op
# in wheel installs and when HUSK_NO_AUTO_BUILD=1).
_ensure_studio_built()
_studio_dist = _find_studio_dist()
if _studio_dist is not None:
    log.info("Serving studio bundle from %s", _studio_dist)

    @app.get("/", include_in_schema=False)
    async def _spa_root() -> FileResponse:
        return FileResponse(_studio_dist / "index.html")

    # SPA fallback: any unknown route under / that isn't an API/WS/asset
    # request returns index.html so wouter / react-router can handle it.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        # Static asset hit (assets/* served by the mount below) — let the
        # mount handle it. We only fall through here on misses.
        if full_path.startswith(("api/", "ws/", "v1/")):
            # Should be matched by routers; if we get here it's a real 404.
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        asset = _studio_dist / full_path
        if asset.is_file():
            return FileResponse(asset)
        return FileResponse(_studio_dist / "index.html")

    # The Vite build emits hashed assets under /assets/*.
    app.mount(
        "/assets",
        StaticFiles(directory=_studio_dist / "assets"),
        name="studio-assets",
    )
else:
    log.info("No studio bundle found; serving dev landing page at /")

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request) -> HTMLResponse:
        port = str(request.url.port or 7654)
        return HTMLResponse(
            _LANDING_HTML
            .replace("__VERSION__", __version__)
            .replace("__PORT__", port)
        )


def attach_run_tail(run_id: str, event_path_str: str) -> None:
    """Helper for the legacy CLI to register a new run before the sandbox spawns.

    Kept for back-compat while husk-sandbox is being retired.
    """
    from pathlib import Path

    from husk_studio_backend.ingest.jsonl_reader import tail_events

    loop = asyncio.get_event_loop()
    loop.create_task(tail_events(run_id, Path(event_path_str)))
