# husk-ai

Visual debugger for AI agents — CLI + bundled Studio. Stop debugging with print
statements.

## Install from source (MVP today)

```bash
git clone https://github.com/husk-ai-team/husk-ai.git
cd husk-ai
uv sync --all-packages
uv run husk-ai start
```

The CLI opens `http://localhost:7654` in your browser. Click *Try free* on the
Welcome screen and you're in — no signup needed.

A one-line `pip install husk-ai` is on the roadmap.

## Commands

```
husk-ai start    Boot the backend and open the Studio.
husk-ai demo     Seed demo fixtures (Cursor pending + OTel trace).
husk-ai list     List recent runs.
husk-ai doctor   Diagnostics (versions, paths, integration health).
husk-ai clean    Wipe ~/.husk/.
```

See the [project README](https://github.com/husk-ai-team/husk-ai) for full
docs, IDE integrations (Cursor, VS Code, Antigravity), and OTel instrumentation
patterns Husk understands.

## License

Source-available under the Business Source License 1.1 (BUSL 1.1). See the
[`LICENSE`](https://github.com/husk-ai-team/husk-ai/blob/main/LICENSE) at the
repository root.
