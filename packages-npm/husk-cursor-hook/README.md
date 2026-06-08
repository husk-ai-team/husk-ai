# husk-cursor-hook

Cursor observability bridge for [Husk](https://husk.dev) — the visual debugger for AI agents.

Streams Cursor's `afterFileEdit` and `stop` events to your local Husk backend
so the Studio timeline shows every file your agent touched, alongside the LLM
and tool calls captured via OpenTelemetry.

This bridge is **observability-only**. It never blocks the Cursor agent and
never returns a decision.

## Install

```bash
npm install -g husk-cursor-hook
```

## Use

In your Cursor project, run:

```bash
husk-cursor-hook install
```

This writes `.cursor/hooks.json` registering the observability events with
Cursor.

Then start Husk:

```bash
# Install from source (PyPI release is on the roadmap)
git clone https://github.com/husk-ai-team/husk-ai.git && cd husk-ai
uv sync --all-packages
uv run husk-ai start
```

Open `http://localhost:7654` to see the Studio.

## How it works

Each registered Cursor hook event runs `husk-cursor-hook hook --event=<name>`.
The script POSTs the payload to `http://localhost:7654/api/cursor/events` as
fire-and-forget, then writes an empty JSON response to stdout so Cursor
proceeds immediately.

If Husk isn't running, the bridge logs to stderr and exits cleanly — your
Cursor session is never affected.

## Environment

- `HUSK_URL` — override the Husk backend URL (default `http://localhost:7654`).
