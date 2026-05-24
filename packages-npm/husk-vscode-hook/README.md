# Husk for VS Code

The Husk bridge for **VS Code**, **Antigravity** (Google's VS Code fork),
and any other VS Code-compatible IDE.

Streams every terminal command your AI agent runs — including commands
fired by Copilot, Continue, Cline, Roo, or Antigravity's native agent —
into the Husk Studio at `http://localhost:7654`. You see what your agent
actually did, with arguments and cwd, in the same activity feed as your
LangGraph runs and OTel spans.

## Install

1. Have Husk running locally:
   ```bash
   git clone https://github.com/husk-ai-team/husk-ai.git && cd husk-ai
   uv sync --all-packages
   uv run husk-ai start
   ```
2. Install this extension in your IDE (VS Code, Cursor, Antigravity, …):
   ```bash
   code --install-extension husk-vscode-hook
   ```
   (Or open the marketplace, search "Husk".)
3. Open any terminal in the IDE. The status bar shows `● Husk` once the
   extension can see your local backend.

## What you get today

| Capability | Status |
|---|---|
| Stream every terminal command into Husk Studio | ✅ |
| Tag events by IDE (vscode / cursor / antigravity) | ✅ |
| Pause an agent before a destructive command (Allow / Deny banner) | ❌ — see below |
| Group commands by run / agent thread | ⏳ roadmap |

The "Allow / Deny" banner ships only on **Cursor** today, because Cursor
exposes a pre-tool-execution
hook ([packages-npm/husk-cursor-hook](../husk-cursor-hook)). VS Code and
Antigravity don't expose that hook yet. The moment they do (or the
moment Continue / Cline / Roo expose theirs), we'll publish a new
version that plugs in.

If you want active intervention right now, use Cursor + Husk.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `husk.url` | `http://localhost:7654` | Where to send events. Override if you ran `husk start --port <other>`. |
| `husk.captureTerminal` | `true` | Toggle terminal capture. Use `Husk: Toggle Terminal Capture` from the command palette. |

## Commands

- `Husk: Open Studio` — opens the Husk Studio in your browser
- `Husk: Reconnect` — re-pings the backend if you restarted it
- `Husk: Toggle Terminal Capture` — turn capture on/off temporarily

## Privacy

The extension only talks to the URL you set in `husk.url`, which
defaults to your own `localhost`. Commands and cwd never leave your
machine.

## License

Source-available under the Business Source License 1.1 (BUSL 1.1). See the
[`LICENSE`](https://github.com/husk-ai-team/husk-ai/blob/main/LICENSE) at the
repository root.
