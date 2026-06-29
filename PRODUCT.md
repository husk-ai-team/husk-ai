# Husk — Product overview

The complete picture of what Husk is: a local-first, single-user, development-time
debugger for someone who builds AI agents. Every capability below is tagged with its status.

**Status legend**
- ✅ **Present** — built and verified.
- 🔨 **Present (finalizing)** — specced and handed to a follow-up session to close; treated as present, not roadmap.
- 🧭 **Roadmap** — genuinely future, not built.

---

## 1. Positioning

**One line.** Husk is the local debugger you use *while building* an AI agent: it replays
every run as a plain-language story — what the agent did, what it cost, which model handled
each step — and when a run fails, it debugs the run for you. No traces to read.

**Killer feature, one sentence.** Your agent does the wrong thing; click once and Husk reads
the whole run and tells you, in plain language, what went wrong and what to change.

**Who it is for.** One person: a product manager who *uses* AI agents and needs to debug
their own. They build agents mostly with no-code or hosted builders, so the interface speaks
in plain language — runs, steps, costs, and a root cause — not raw spans or code. There is no
team, no second seat, no "supervisor" watching someone else's agents. It is a single user on
their own machine.

**When it is used.** During development, before production. You run the agent you are
building, look at what it did, find why it broke, and fix it — then ship. Husk is not
production monitoring and cannot be turned into it (see §2).

**Tone.** Calm, plain-language, technical. Honest: the automatic debugger is assistance
grounded in the run's real data, and it shows the evidence it used; it is never presented as
certainty.

**Anti-references.** A trace viewer or observability dashboard for engineers (Grafana,
SigNoz, Langfuse). Those read live/production telemetry and assume the reader speaks spans.
Husk's wedge is the opposite: a development-time debugger for a non-engineer, with an AI layer
that does the debugging instead of handing you a trace.

## 2. Principles (hard constraints)

- **Local-first, single-user.** Everything runs and stays on the user's own machine. One
  process, one SQLite file, one person.
- **Development only — enforced in code, not just claimed.** Trace ingest is loopback-only:
  only an agent running on *this* machine can stream in. A deployment on another host is
  refused at the door. Husk cannot be pointed at production by design.
- **Zero data retention.** The only outbound call is the automatic debugger's, to a model
  provider the user configures and brings their own key for.
- **Never self-hosts a model.** The AI layer always calls a configured external provider
  (Regolo.ai by default: EU, GDPR, zero retention).
- **Framework-agnostic.** Nothing in the core depends on any one framework. OpenTelemetry
  GenAI is the normalized vocabulary; LangGraph is one adapter among many.
- **Honesty.** Only call something "replay" where it re-executes; label runs that can only be
  stepped through; never claim a capability the engine does not provide. Connecting an agent
  is a one-line SDK/OpenTelemetry step — it is the single setup touchpoint, not "no code."

## 3. Feature catalog

### 3.1 Instrumentation and framework support
- ✅ **One line to connect.** `from husk_shared import instrument_openai; instrument_openai()`
  and every call streams into Husk. This one line is the only code step; everything after
  happens in the Studio, in plain language.
- ✅ **Generic OpenTelemetry path.** Any agent emitting OTel GenAI works with no adapter: set
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:7654` (loopback only).
- ✅ **One-line SDK adapters.** `instrument_openai()`, `instrument_anthropic()`,
  `instrument_langgraph()`, `instrument_llamaindex()` — thin wrappers over OpenInference
  instrumentors, installed as extras (`husk-shared[openai]`, etc.). Core stays dependency-light.
- ✅ **Native-OTel frameworks.** CrewAI, Pydantic AI, Google ADK and similar connect by
  pointing the OTLP endpoint at the local backend. Honest coverage in `docs/instrumentation.md`.
- 🧭 **More bundled adapters.** AutoGen, Semantic Kernel, Letta, VoltAgent, Cheshire Cat,
  Vercel AI SDK (JS), and deeper framework-specific enrichment.

### 3.2 Seeing a run
- ✅ **Every run as a step-by-step visual.** What the agent did, in plain language — not a
  wall of raw trace spans.
- ✅ **Per-run timeline and node graph.** The order of steps, the state at each, and per-node
  state diffs.
- ✅ **Real-time for the run in front of you.** A WebSocket span stream shows an in-flight run
  as it happens; polling pauses when the tab is hidden, and the first load always runs.

### 3.3 Multi-model attribution (a differentiator)
- ✅ **Per-step capture.** Model and provider, tokens, and cost recorded on every step.
- ✅ **Which model handled each call.** Within a single run, see which model handled each step
  and what each one cost — the fastest way to find the call that gave the wrong answer.
- ✅ **Per-run model breakdown.** "Models in this run": calls, tokens, cost, cost share, and
  errors per model, so a multi-model run's spend is attributable model by model.
- 🧭 **Modality first-class.** Capture, filter, and cost by text/image/audio per step.
- 🧭 **Cached-token tracking.** Where the provider exposes served-from-cache tokens.

### 3.4 Automatic debugging (the killer feature)
- ✅ **Auto-debugger.** On a failed run, Husk reads the whole run, localizes the failing step,
  classifies the failure, explains the root cause with evidence from the run, and proposes a
  fix (a unified diff when the agent's source is available). It *does* the debugging — it is
  not merely an explanation. BYOK; opt-in apply-fix writes the change to the source with a
  backup.
- ✅ **Auto-debug on failure.** Optional: the debugger runs the moment a run errors, with no
  click.
- ✅ **Grounded in the run's real data.** The debugger works from that run's spans, prompts,
  completions, and error — and surfaces the evidence it used, so the root cause can be checked
  against the run.
- ✅ **Provider-configurable, Regolo default.** Anthropic, OpenAI, OpenRouter as alternatives.
  BYOK stored locally in `~/.husk/secrets.json`; never self-hosts a model, never sent to any
  Husk server.
- 🧭 **Self-correcting loop.** The agent fails and Husk drives an automatic correction attempt.
- 🧭 **Human-in-the-loop security gate.** An approval gate on destructive proposed actions
  (file removal, shell commands) before apply-fix runs them.

### 3.5 Modify and replay, and branching
- ✅ **Modify-and-replay.** Re-run from any checkpoint with edited state; the original run is
  preserved and can be re-forked.
- ✅ **Token-bypass.** On Husk's own engine, replay resumes at the fork node and re-runs only
  it and its successors, deterministically skipping the upstream token cost (committed
  benchmark: **42.1% mean token bypass, 6.9× median speed-up, 100% replay success**).
- ✅ **Model-free replay.** Cassettes serve recorded provider responses for deterministic, $0
  replays.
- ✅ **Branching, diff, and lineage.** Parent/child links with token-bypass and cost-saved figures.
- ✅ **Two honest tiers.** True replay for runs on Husk's engine; visual step-through for
  OTel-only runs (no graph module, cannot re-execute), labeled as such.
- 🧭 **True replay for more frameworks** that support deterministic resume.

### 3.6 MCP integration
- ✅ **One-line MCP server.** `husk-ai mcp install --client <claude-code|cursor|…>`. Read-only,
  local-first tools (`list_runs`, `get_run`, `get_trace`, `get_span`, `list_errors`,
  `cost_breakdown`, …) so the coding agent you already debug in can read your runs without
  trace-scrolling. Reads `~/.husk/traces.db` directly, so it works even when the backend is
  not running. The `replay_run` tool re-invokes your code and is gated behind an explicit flag.

### 3.7 Deployment
- ✅ **One-command Docker.** GHCR image (`ghcr.io/husk-ai-team/husk-ai`); `docker run …` or
  `docker compose up -d`. Loopback ingest is preserved — it stays a local development tool.
- ✅ **SQLite by default.** A single local file at `~/.husk/traces.db`; one process is the only
  writer.

### 3.8 Design and docs
- ✅ **Black-and-white Studio.** One monochrome, ink-on-paper system across the app.
- ✅ **Docs as a navigable set.** A tight, value-first README plus `docs/` topic pages.
- ✅ **AGENT_PROMPT.md.** A brief to drop into a coding assistant's rules so it reaches for
  Husk when you debug.

## 4. Architecture (brief)

```
your agent  ──OTLP (loopback only)──▶  FastAPI backend  ──serves──▶  React Studio (B&W)
(any framework)                         on 127.0.0.1:7654            runs · timeline · graph · replay
                                              │
                                              ├── normalize spans  ──▶  SQLite  (~/.husk/traces.db)
                                              ├── replay engine    ──▶  Husk's own checkpoint store
                                              └── auto-debugger     ──▶  your BYOK provider (the only outbound call)
```

One FastAPI process binds `127.0.0.1:7654`: it ingests telemetry (loopback only), serves the
Studio, runs replays, and calls the configured provider for the automatic debugger. Trace
ingest, replay, and the debugger are all loopback-only, so Husk only ever sees an agent
running on this machine and cannot be pointed at a production deployment. Nothing core depends
on a framework. Full map in `docs/architecture.md`.

## 5. What is present vs roadmap, at a glance

**Present (built or finalizing):** one-line instrumentation and the generic OTLP path, the
step-by-step run view with timeline and node graph, the multi-model per-step attribution and
per-run breakdown, the automatic debugger (manual and auto-on-failure, BYOK, apply-fix),
modify-and-replay with token-bypass / model-free cassettes / branching, the MCP read server,
the Regolo-default provider layer, the black-and-white Studio, the docs set, and Docker.

**Roadmap:** modality (image/audio) first-class, cached-token tracking, the self-correcting
debug loop and the human-in-the-loop security gate, more bundled framework adapters, and true
replay for more frameworks.

## 6. Definition of done (overall)

A single person, on their own machine, connects the agent they're building with one line of
setup and runs it. In the Studio they see each run as a step-by-step visual — what it did,
what it cost, and which model handled each step — without reading a trace. When a run fails,
they click once (or have already turned on auto-debug) and Husk reads the whole run and tells
them, in plain language, the root cause and what to change, with the evidence it used; if the
source is available, it proposes a diff they can apply. They edit a step and replay from there,
skipping the upstream token cost. Nothing core depends on one framework, no model is
self-hosted, ingest is loopback-only so it can never be production monitoring, and the only
data that leaves the machine is the debugger's BYOK call to the provider they chose.
