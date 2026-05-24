from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from husk import __version__
from husk.config import db_path, husk_home

console = Console()


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )


@click.group()
@click.version_option(__version__, prog_name="husk")
@click.option(
    "--log",
    "log_level",
    default="info",
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    envvar="HUSK_LOG",
    help="Log verbosity (env HUSK_LOG).",
)
def main(log_level: str) -> None:
    """Husk — the visual debugger for AI agents."""
    _setup_logging(log_level)


@main.command()
@click.option("--port", default=7654, type=int, help="Backend port (default 7654).")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--no-open-browser", is_flag=True, help="Do not auto-open the browser.")
def start(port: int, host: str, no_open_browser: bool) -> None:
    """Boot the Husk backend and open the Studio in your browser."""
    from husk.server import start_server

    try:
        start_server(host=host, port=port, open_browser=not no_open_browser)
    except KeyboardInterrupt:
        console.print("\n[dim]Husk stopped.[/dim]")
        sys.exit(0)


@main.command(name="list")
@click.option("--limit", default=20, type=int)
def list_runs(limit: int) -> None:
    """List recent runs."""
    from husk_studio_backend.db.engine import sync_session
    from husk_studio_backend.db.models import RunRow

    with sync_session() as s:
        rows = s.query(RunRow).order_by(RunRow.started_at.desc()).limit(limit).all()

    table = Table(title=f"Husk runs ({len(rows)})")
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("framework")
    table.add_column("status")
    table.add_column("tokens")
    table.add_column("cost (USD)")
    for r in rows:
        table.add_row(
            r.id,
            r.framework or "-",
            r.status,
            f"{(r.total_tokens_in or 0) + (r.total_tokens_out or 0)}",
            f"${r.total_cost_usd or 0:.4f}",
        )
    console.print(table)


@main.command()
def doctor() -> None:
    """Diagnostics: versions, paths, integration health."""
    home = husk_home()
    db = db_path()
    console.print(f"husk: [cyan]{__version__}[/cyan]")
    console.print(f"home: {home}")
    if db.exists():
        console.print(f"db:   {db}  [green]ok[/green]")
    else:
        console.print(f"db:   {db}  [yellow]missing (created on first `husk start`)[/yellow]")


@main.command()
@click.option("--url", default="http://127.0.0.1:7654", help="Husk backend URL.")
def demo(url: str) -> None:
    """Seed demo fixtures so the Studio has a fresh narrative to show.

    Posts a pending Cursor intervention (for the banner) and runs the bundled
    LangGraph example. Requires `husk start` to be running.
    """
    import httpx

    base = url.rstrip("/")

    try:
        h = httpx.get(f"{base}/api/health", timeout=2.0)
        h.raise_for_status()
    except Exception as e:  # noqa: BLE001
        console.print(
            f"[red]Husk backend not reachable at {base}[/red]\n"
            f"Start it first: [cyan]husk start[/cyan]\n({e})"
        )
        sys.exit(1)

    # 1. Pending Cursor intervention — drives the red banner.
    cursor_payload = {
        "hook": "beforeShellExecution",
        "project": "my-startup-demo",
        "payload": {
            "command": "rm -rf node_modules",
            "cwd": "C:\\Users\\demo\\my-startup-demo",
            "conversation_id": "demo-conv-1",
            "model": "claude-sonnet-4-6",
        },
    }
    r = httpx.post(f"{base}/api/cursor/events", json=cursor_payload, timeout=5.0)
    r.raise_for_status()
    event_id = r.json().get("event_id")
    console.print(f"  · seeded Cursor intervention [dim](id={event_id})[/dim]")

    # 2. Self-contained OTel trace emission — no extra deps beyond what
    #    husk-ai already installs (opentelemetry-sdk + OTLP/HTTP exporter).
    #    Emits a 3-span agent.run with GenAI v1.36 attributes so the run
    #    appears in /runs with realistic prompts, completions, and costs.
    console.print("  · emitting demo trace (3 spans, GenAI v1.36 attrs)…")
    try:
        _emit_demo_trace(base)
    except Exception as e:  # noqa: BLE001
        console.print(f"    [yellow]demo trace skipped: {e}[/yellow]")

    console.print("\n[green]Demo data ready.[/green]")
    console.print(f"Open the Studio: [cyan]{base}[/cyan]")
    console.print(
        "[dim]The intervention banner appears at the top; the run is under /runs.[/dim]"
    )


def _emit_demo_trace(base: str) -> None:
    """Send a fully-formed OTel trace to the local Husk backend.

    No reliance on the examples/ directory — works out of the box for users
    who installed via `pip install husk-ai`.
    """
    import random as _random
    import time as _time

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = f"{base.rstrip('/')}/v1/traces"
    resource = Resource.create({"service.name": "husk-ai-demo"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    # Use a fresh tracer namespace to avoid clashing with any global setup.
    tracer = provider.get_tracer("husk.cli.demo")

    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "husk-ai-demo")
        root.set_attribute("gen_ai.system", "openai")

        with tracer.start_as_current_span("chat gpt-4o-mini (plan)") as s:
            s.set_attribute("gen_ai.system", "openai")
            s.set_attribute("gen_ai.operation.name", "chat")
            s.set_attribute("gen_ai.request.model", "gpt-4o-mini")
            s.set_attribute("gen_ai.response.model", "gpt-4o-mini")
            s.set_attribute("gen_ai.usage.input_tokens", 42)
            s.set_attribute("gen_ai.usage.output_tokens", 18)
            s.add_event("gen_ai.user.message", {
                "content": "What's the capital of Italy and how many people live there?",
            })
            s.add_event("gen_ai.choice", {
                "finish_reason": "stop",
                "message.content": "I'll look up the population, then answer.",
            })
            _time.sleep(_random.uniform(0.05, 0.12))

        with tracer.start_as_current_span("tool: web_search") as s:
            s.set_attribute("gen_ai.tool.name", "web_search")
            s.set_attribute("gen_ai.tool.type", "function")
            s.add_event("gen_ai.tool.message", {
                "name": "web_search",
                "arguments": '{"q": "Rome population"}',
                "content": "Rome (Roma), Italy. Population: ~2.87M (2024).",
            })
            _time.sleep(_random.uniform(0.02, 0.05))

        with tracer.start_as_current_span("chat gpt-4o (answer)") as s:
            s.set_attribute("gen_ai.system", "openai")
            s.set_attribute("gen_ai.operation.name", "chat")
            s.set_attribute("gen_ai.request.model", "gpt-4o")
            s.set_attribute("gen_ai.response.model", "gpt-4o")
            s.set_attribute("gen_ai.usage.input_tokens", 88)
            s.set_attribute("gen_ai.usage.output_tokens", 64)
            s.add_event("gen_ai.user.message", {
                "content": "Compose the final answer using the search result.",
            })
            s.add_event("gen_ai.choice", {
                "finish_reason": "stop",
                "message.content": "Rome is the capital of Italy; ~2.87 million people live there.",
            })
            _time.sleep(_random.uniform(0.05, 0.12))

    provider.shutdown()


@main.command()
def clean() -> None:
    """Remove the local Husk database and runs directory."""
    home = husk_home()
    db = db_path()
    if not click.confirm(f"Delete Husk data under {home}? This is irreversible."):
        return
    import shutil

    if db.exists():
        db.unlink()
    runs = home / "runs"
    if runs.exists():
        shutil.rmtree(runs)
    click.echo("Cleaned.")


if __name__ == "__main__":
    main()
