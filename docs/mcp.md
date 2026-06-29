# MCP Server

Husk ships an [MCP](https://modelcontextprotocol.io) server, so the coding agent you build with can read your own runs without you leaving the assistant. Ask "which of my last runs failed, and why?" and the agent reads the answer straight from Husk, no trace-scrolling required.

This is the bridge between Husk's local trace database and the AI tools you already debug in. Claude Code, Cursor, Claude Desktop, and Windsurf can all list runs, inspect a single run's trace, and break down its cost on demand.

The server runs locally over stdio and reads `~/.husk/traces.db` directly, so the read tools work even when `husk-ai start` is not running. Like the rest of Husk, it is a development-time tool: it reads runs captured on this machine, and the backend it talks to refuses any non-loopback caller.

## Quickest path: let Husk write the config

The install command writes the client config for you and resolves the correct absolute path to the binary (which matters for a source install):

```bash
husk-ai mcp install --client claude-code      # or: cursor, claude-desktop, windsurf
```

## Wire it by hand

The launch command is `husk-ai mcp`. Most clients (Cursor, Claude Desktop, Windsurf) read an MCP config file, so add Husk under `mcpServers`:

```json
{
  "mcpServers": {
    "husk": { "command": "husk-ai", "args": ["mcp"] }
  }
}
```

Claude Code takes it as one command:

```bash
claude mcp add husk -- husk-ai mcp
```

## Tools exposed

All read-only and local-first:

| Tool | What it returns |
| --- | --- |
| `list_runs` | Your recent agent runs, newest first. |
| `get_run` | One run's status, cost, tokens, and timing. |
| `get_trace` | The full span tree for a run — what the agent did, step by step. |
| `get_span` | A single span's untruncated inputs, outputs, error, and metadata. |
| `list_errors` | Recent failed runs and the spans where they broke. |
| `cost_breakdown` | Token and USD spend for a run, grouped by model — the fast way to find which call cost what. |
| `list_cursor_events` | Recorded editor events (file edits, stop signals) for context. |

A "run" is one agent execution; a "span" is one step within it (an LLM call, a tool call, a graph node). Timestamps are Unix milliseconds.

## Make your assistant actually use them

Connecting the server is not enough. Drop [`AGENT_PROMPT.md`](../AGENT_PROMPT.md) into your assistant's rules (`CLAUDE.md`, a `.cursor/rules/` file, and so on) so it reaches for Husk when you are debugging instead of guessing.

## Replay is off by default

`replay_run` re-invokes your agent and runs your code, so it is gated behind an explicit flag and intended for local use only:

```bash
husk-ai mcp --enable-replay            # or: HUSK_MCP_ENABLE_REPLAY=1
```

When enabled, it re-runs a recorded graph from a chosen step with edited state, deterministically skipping the upstream token cost — the same modify-and-replay flow as the Studio. It needs the backend running (`husk-ai start`), and the backend executes that code only for loopback callers.

## Source clone note

Working from a source clone (no `pip install husk-ai` yet)? Prefix with `uv run`, for example `uv run husk-ai mcp install --client cursor`. The install command writes the absolute path to the venv binary, so the client can still launch it.

## See also

- [README](../README.md) for the full Husk overview.
- [CLI reference](./cli.md) for every `husk-ai` command.
- [Replay](./replay.md) for what `replay_run` does once enabled.
