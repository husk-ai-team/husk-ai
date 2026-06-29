# Glossary

Plain-language definitions for the terms you'll meet in Husk. You build agents
mostly with no-code or hosted builders, so most of these come up only in passing.
The first few are the ones that matter; the rest are here when you need them.

For the bigger picture, see the [README](../README.md).

## The core idea

**Agent**
A program that calls an LLM in a loop and uses the model's output to decide what
to do next: call a tool, edit a file, run a command, write code. You point Husk at
the agent you're building, on this machine, and it records each run so you can
step through it.

**LLM (Large Language Model)**
The AI "brain" behind an agent (GPT-4o, Claude, Gemini, Llama). Text goes in, text
comes out. A single agent can use several models for different steps; Husk shows
which one handled each call.

**Prompt**
The text sent to an LLM: system instructions, the user's question, and the prior
conversation. When an agent misbehaves, the prompt is often where the cause lives.

**Tool call**
When the LLM decides "call function X with these arguments" and the agent runs X
(a search, an API request, a database query). Husk renders each tool call as its
own step, so you can see exactly what the agent did and what came back.

## What Husk does

**Automatic debugger (auto-debugger)**
Husk's headline feature. When a run fails, the automatic debugger reads the whole
run and tells you, in plain language, what went wrong and what to change. It does
the debugging for you — it's not just an explanation of a trace. Click once, or
flip on auto-debug and it runs the moment a run fails. It uses an LLM through a key
that stays on your machine, and it's the only part of Husk that calls out to a
provider.

**Model attribution**
Within a single run, Husk shows which model handled each step and what each step
cost. When a multi-model agent gives a wrong answer, this is the fastest way to
find the call that produced it.

**Studio**
The web UI Husk serves at `/`. Where you open a run, inspect each step, run the
automatic debugger, and step through a recording. See the [README](../README.md)
for the tour.

**Run**
One recorded execution of your agent: the tree of steps from start to finish, with
prompts, completions, tool I/O, token counts, and cost. The unit you open, inspect,
debug, and replay.

**Replay**
Re-running a recorded run to see what happened, or editing one input and running it
again from the broken step to test a fix (modify-and-replay). On Husk's engine,
replay resumes from the snapshot before the step you forked at and re-runs only that
step and its successors, so the upstream token cost is skipped. With a cassette it's
also deterministic: the same recording produces the same result with no live model
call.

**Branch**
Every true replay forks a new run off the original rather than overwriting it. The
parent run stays intact and the new run is recorded as a child at the step you
chose. You can fork the same parent many times and compare the trajectories side by
side.

**Snapshot**
A copy of the agent's state saved before a step runs. Husk's engine writes one
before each step so a run can be resumed, or replayed, from that point.

**Cassette**
A store of the provider HTTP responses recorded during a run. With cassettes
enabled, a replay serves its LLM calls from the recording — deterministic,
byte-identical, and $0. A call you changed (because you edited the state) falls
through to the real provider and is recorded into the cassette for next time.

## Framework and protocol terms

Husk is framework-agnostic. Anything that emits standard telemetry can connect, and
no part of the core depends on any single framework. Connecting an agent is a
one-line SDK / OpenTelemetry setup step — the single touchpoint where you wire the
agent to Husk.

**OpenTelemetry (OTel)**
The industry-standard telemetry protocol. Any framework that "speaks OTel" streams
its internal events to Husk as spans.

**Span**
One unit of work in OTel: a single LLM call, a single tool call, a single agent
decision. A run is a tree of spans.

**OTLP (OpenTelemetry Protocol)**
The wire format spans are sent in. Husk accepts OTLP over HTTP on port `7654`.
Ingest is loopback-only: only an agent running on this machine can stream in, so
Husk cannot be pointed at a deployment on another host.

**GenAI semantic conventions**
OTel's spec for AI and LLM apps: standard names for prompts, completions, token
counts, and the like. They're why Husk can read tokens and cost from any compliant
framework without custom glue.

**Adapter**
A small connector that maps one framework's events into Husk. There are several;
LangGraph is just one of them, not a dependency of the core.

**Hook**
A function that fires at a specific moment inside another program. For example,
Cursor's hooks let Husk capture file edits and stop signals as an agent works.

**Cursor**
An AI code editor (a VS Code fork) with a built-in agent. Husk subscribes to its
hooks so file edits and stops appear on the timeline.

## Privacy and hosting

**Local-first**
Husk runs on your own machine. Your runs, prompts, and keys stay there. Ingest is
loopback-only by design, so Husk is a development-time tool — it can't be pointed at
production.

**Zero data retention**
Husk doesn't keep your data beyond your own storage, and it doesn't phone home. The
only outbound call is the automatic debugger's, to a provider you choose.

**BYOK (bring your own key)**
You supply the API key for the model the automatic debugger uses. The key stays on
your machine; Husk never ships it anywhere except the provider you point it at.

**Regolo.ai**
The default provider for the automatic debugger: EU-based, GDPR-aligned, and
zero-retention. You can point Husk at a different provider if you prefer.

## Tooling you may see in setup

**Terminal**
A text window where you type commands instead of clicking.

**git**
Source-control tool. Used here to download Husk's code in one command.

**uv**
A fast Python toolchain by Astral. It installs Python for you and manages
dependencies.

**Python**
The language Husk's core is written in. You don't need to write Python to use Husk.

**Node.js**
A JavaScript runtime, needed only for the Cursor bridge and building the Studio UI.
Husk's core API runs without it.

---

Stuck on a term not covered here? Open an issue on
[GitHub](https://github.com/husk-ai-team/husk-ai/issues).
