# Husk documentation

A navigable wiki for Husk: the local, single-user debugger you run **while building** an AI
agent, before it ships. Connect your agent, run it, and Husk replays every run as a visual
story — what it did step by step, which model handled each call and what it cost, and, when
something breaks, an automatic debugger that reads the whole run and tells you in plain
language what went wrong and what to change. Start at the [project README](../README.md) for
the overview.

Development only — never production. Trace ingest is loopback-only, so only an agent running
on your own machine can stream in; a deployment on another host is refused at the door. Husk
is not, and cannot be, production monitoring.

## Start here

- [Getting started](./getting-started.md) — install, run, and see your first run.
- [Instrumentation & frameworks](./instrumentation.md) — connect your agent: the one-line SDK
  adapters, the generic OpenTelemetry path, and the framework coverage matrix.

## Using Husk

- [Multi-model attribution](./multi-model.md) — which model ran each step, and what each cost.
- [Modify & replay](./replay.md) — re-run from a checkpoint with edited state; the two honest tiers.
- [MCP](./mcp.md) — connect Husk to your AI coding tools.

## Operate

- [Docker](./docker.md) — run with Docker and docker compose.
- [Security & data](./security.md) — the loopback model; what stays on your machine and what leaves it.
- [Architecture](./architecture.md) — how the pieces fit.
- [CLI](./cli.md) — the `husk-ai` command reference.

## Reference

- [Troubleshooting](./troubleshooting.md)
- [Glossary](./glossary.md)

Setting Husk up on your machine? Hand an AI assistant [AGENT.md](../AGENT.md).
