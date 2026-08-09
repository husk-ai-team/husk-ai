# Security and data model

Husk is a local-first, single-user, development-time debugger. It runs on your own machine, sees only an agent running on that same machine, and keeps your data there. This page describes exactly what is exposed on the network, why Husk cannot be pointed at production, where your trace data lives, and the one place data leaves your machine: the automatic debugger's call to a model provider you configure.

The short version:

- The backend binds loopback (`127.0.0.1`). Nothing is reachable from another machine, another network, or a web page you happen to visit.
- Trace ingest, replay, and the debugger are all loopback-only. Only an agent running on **this** machine can stream traces in; a deployment on another host is refused at the door. This is development-time tooling by design — it is not, and cannot be, production monitoring.
- Trace data (prompts, completions, tool I/O) is stored in cleartext under `~/.husk` with owner-only permissions. Common secret shapes are redacted on ingest.
- The only outbound calls are the automatic debugger's, to the model provider you configure (Regolo.ai by default: EU-hosted, GDPR, zero data retention).
- There is no telemetry back to Husk and no cloud account. Deleting `~/.husk` removes all stored state.

## Loopback by default

By default the backend binds `127.0.0.1:7654`. It is not reachable from another machine, another network, or a web page you happen to visit.

Trace ingest, replay, and the debugger are protected by a single loopback guard that enforces two checks:

1. The peer must be loopback. A request from any non-loopback address is refused with `403`. This holds even if you start the backend with `--host 0.0.0.0`.
2. If an `Origin` header is present (so a browser made the request), its host must be loopback too. A page using DNS rebinding to reach `127.0.0.1` still carries its attacker origin in the `Origin` header, so the host check rejects it while the Studio (served from localhost on any port) passes.

Non-browser clients (the OpenTelemetry exporter, the MCP server, curl) send no `Origin` and connect from loopback, so they work unchanged.

This is why the read tools in the [MCP server](./mcp.md) and the [replay engine](./replay.md) are safe to leave running: a website cannot drive them.

**What the guard does and does not cover, precisely.** It is applied to the three routers that ingest data, execute code, or hold your key: trace ingest (`/v1/traces`), replay (`/api/replay`), and the debugger (`/api/debugger/*`). The read-only routes (runs, spans, graph, branches, diff, dashboard, integrations), the IDE-events POST, and the trace WebSocket do not carry it — they are protected by the loopback bind itself and by CORS pinned to `localhost:5174`. That is a deliberate split: the guard's Origin check exists to stop a malicious web page from *writing* or *executing*, and the routes without it can do neither. It does mean that if you deliberately bind the backend to a routable interface, the read routes are the ones exposed first.

## Development-only by design

Husk is a tool you use **while building** an agent, before it ships. That is enforced in code, not just claimed.

Trace ingest (`POST /v1/traces`, OTLP/HTTP) sits behind the same loopback guard as replay and the debugger. So only an agent running on this machine can stream traces in. There is no networked, keyed ingest endpoint a remote host could authenticate against — point a production deployment on another machine at Husk and it is refused. Husk sees a single agent, on your box, while you build it.

Connecting that agent is a one-line setup step: the SDK adapter or a generic OpenTelemetry exporter pointed at `127.0.0.1:7654`. See [Instrumentation](./instrumentation.md) for the snippet. That is the single setup touchpoint; from there the trace stays local.

## Where data lives

Everything Husk records lives under `~/.husk/` on your machine:

- `traces.db`: runs and spans, including prompts, completions, and tool I/O, stored as cleartext JSON.
- `cassettes/`: recorded provider HTTP responses for model-free [replay](./replay.md).
- `secrets.json`: the automatic debugger's bring-your-own-key config (provider, model, and your provider API key).

`~/.husk` sits outside the repository, so none of it is ever committed. On POSIX systems `secrets.json` is written with `0600` (owner read/write only). **On Windows there is no equivalent** — `0600` is a POSIX mode and does not apply, so the file inherits the permissions of your user profile directory. Any process running as you can read it. Treat `~/.husk` as sensitive on every platform: it contains your raw run data and your provider key in cleartext, by design, so that the data stays under your control and never round-trips through a Husk-operated server. Nothing in `~/.husk` is encrypted at rest.

There is no telemetry back to Husk and no cloud account. Deleting `~/.husk` removes all stored state.

## Secret-shape redaction on ingest

Recorded prompts, completions, and tool I/O can contain provider keys or tokens that an agent pasted into a request. Before any span is persisted, Husk scrubs common secret shapes from the recorded text and replaces them with `***REDACTED***`. The patterns cover the usual formats:

- Anthropic (`sk-ant-…`) and OpenAI-style (`sk-…`) keys
- AWS access key IDs (`AKIA…`)
- Google API keys (`AIza…`)
- GitHub personal access tokens (`ghp_…`)
- Slack tokens (`xox[baprs]-…`)
- `Authorization: Bearer …` headers
- `api_key` / `secret` / `token` / `password` assignments

This is a coarse net, not a guarantee. It catches the common key and token formats, not arbitrary user PII. Redaction runs before the data is written to `traces.db` and before any text is shipped to the automatic debugger, so a redacted secret is gone from both.

To disable redaction (for example, when you need the exact raw payload for debugging and you trust the local store), set `HUSK_NO_REDACT=1`.

## The one place data leaves your machine

The automatic debugger is the only feature that makes an outbound call. When it analyzes a failed run — on a click, or automatically the moment a run fails if you turn on auto-debug — Husk sends that run's context (relevant prompts, completions, and the agent's source) to the model provider you configured. That is the single point where data leaves your machine.

This layer is bring-your-own-key:

- The default provider is **Regolo.ai**: EU-hosted, GDPR-compliant, with zero data retention. Your run data leaves only to an EU provider, and only for analysis.
- **Anthropic**, **OpenAI**, and **OpenRouter** remain selectable in Settings if you prefer them.
- Your key is stored locally in `~/.husk/secrets.json` and is never sent to any Husk server. An environment variable (`REGOLO_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) is honored as a fallback so a key already in your shell works without re-entry. **OpenRouter has no environment-variable fallback** — set its key in Settings.
- The key is never logged and never returned to the UI. The Studio only ever sees `has_key: true/false`, never the key itself.

If you never run the debugger, no data leaves your machine at all. The bundled examples, multi-model attribution, and replay all work with no key.

## Replay executes code

Replay re-imports and runs your agent's code, so it is treated as a sensitive operation. It stays loopback-only, and it will only import graph modules located under your project directory (or the directories you list in `$HUSK_ALLOWED_GRAPH_DIRS`). This prevents a crafted trace from pointing replay at an arbitrary file on disk. A replay request may also carry ephemeral environment overrides (so a run can be replayed with a provider key the backend didn't boot with), and those are restricted to a fixed allow-list of known provider API-key names — a request cannot inject an arbitrary variable into the process. Note the flip side: replay executes in the backend's own process, so the graph it re-imports sees the environment that process already has. See [Replay](./replay.md) for the execution model and the model-free cassette mode that avoids real provider calls entirely.

## Checklist for a safe setup

- Leave the backend on loopback. Husk is built to be reached only from your own machine.
- Keep your provider key in `~/.husk/secrets.json` (or a shell environment variable). It never leaves the host except as the debugger's outbound call to the provider you chose.
- Restrict filesystem access to `~/.husk`. It holds cleartext run data and your provider key.
- Choose your debugger provider deliberately. Regolo (EU, zero retention) is the default; switch only if your data policy allows it.

## See also

- [Getting started](./getting-started.md): install, run, and land your first trace.
- [Replay](./replay.md): the execution model and cassette-based, $0 replay.
- [MCP server](./mcp.md): the loopback read tools coding agents use.
- [README](../README.md): the full project overview and security model summary.
