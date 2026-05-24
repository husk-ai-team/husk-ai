# husk-cursor-hook

Cursor SDK Hooks bridge for [Husk](https://husk.dev) — the visual debugger for AI agents.

## Install

```bash
npm install -g husk-cursor-hook
```

## Use

In your Cursor project, run:

```bash
husk-cursor-hook install
```

This writes `.cursor/hooks.json` so Husk can intercept Cursor's hook events.

Then start Husk:

```bash
# Install from source (PyPI release is on the roadmap)
git clone https://github.com/EdoardoBambini/husk-ai.git && cd husk-ai
uv sync --all-packages
uv run husk-ai start
```

Open `http://localhost:7654` to see the Studio.

## How it works

Each hook event runs `husk-cursor-hook hook --event=<name>`. The script POSTs
the payload to `http://localhost:7654/api/cursor/events`, then long-polls for
a decision (Allow / Deny / Ask), which you click in the Husk Studio UI.

If Husk isn't running, hooks fail open — your Cursor session is never blocked.

## Environment

- `HUSK_URL` — override the Husk backend URL (default `http://localhost:7654`).
