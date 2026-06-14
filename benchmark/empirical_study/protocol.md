# Empirical study protocol — within-subjects crossover

> **STATUS: INFRASTRUCTURE READY, NOT YET CONDUCTED.**
>
> This subtree contains the full protocol, analysis pipeline, task kit and
> sample data needed to run a rigorous within-subjects crossover study of
> Husk vs baseline MTTR.
>
> **The study has not been run yet** and is **NOT cited in the current
> pitch deck**. The current pitch relies exclusively on the SQL-objective
> hero metrics (DHV / DCS / MRTT) extracted from `benchmark/metrics.sql`.
>
> This study is **post-funding work**: it requires recruiting 12-20
> external engineers (~€1.500 honoraria + ~30h researcher time) which is
> outside the in-house budget of a pre-seed founder team. When the
> resources are available, the protocol below is ready to execute as-is.

## Purpose

Measure the **real** Mean Time To Resolution (MTTR) delta produced by Husk
versus the baseline workflow (terminal logs + manual re-run) when engineers
debug realistic AI-agent failures.

This study replaces the Monte-Carlo simulators (`baseline_replay.py`,
`husk_replay_sim.py`) as the source of MTTR claims in the pitch deck. Those
simulators are calibrated to anecdotal reports; this protocol produces
measurements with statistical significance bounds.

The design is **within-subjects crossover** — the standard methodology used
by Microsoft Research in DX studies (e.g. the "Sharp Tools" study, N=19) to
isolate the tool effect from skill variance.

---

## Participants

- **N = 12–20** software engineers.
- Required experience: Python + LangChain/LangGraph familiarity. Working
  knowledge of `print` debugging, log inspection, and standard IDE
  workflows.
- Recruit from communities where AI-agent debugging is a daily activity
  (LangChain Discord, RAG/LLMOps Slack, AI Engineer Foundation list).
- Compensate participants (gift card / honorarium) to reduce no-show bias.

**Statistical power**: with N=15 and an expected MTTR ratio ≥3×, a paired
T-test reaches p<0.05 power 0.8 on a standard deviation up to ~60 % of the
mean. If N drops below 10, the study is **underpowered** — do not publish
the numbers.

---

## Task kit

Four debugging tasks of **homogeneous complexity**, each rooted in a
realistic agent failure mode. Live in `task_kit/`:

| Task | Failure type | Root cause to find | Difficulty |
|---|---|---|---|
| **T1** — RAG retrieval fail | Empty / wrong-domain retrieval | Wrong vector index loaded; engineer must swap to correct one | ★★★ |
| **T2** — Synthesis hallucination | LLM cites source [9] that doesn't exist | `synthesize` prompt allows citing beyond N sources; engineer must constrain prompt | ★★★ |
| **T3** — Tool JSON parse error | Tool call output is malformed; downstream parsing crashes | Tool returns inconsistent shape on edge case; engineer must add JSON repair / validation | ★★★ |
| **T4** — Multi-hop context loss | Last node lacks information from N-2 because of state merge bug | LangGraph state reducer drops field; engineer must fix the reducer | ★★★ |

Each task includes:
- `README.md` — what the agent does, expected output, observed symptom.
- `agent.py` — the broken agent (working code, broken behaviour).
- `failing_input.json` — the input that triggers the failure.
- `expected_fix.md` — sealed envelope (used to grade resolution, not shown).

---

## Crossover design

Participants are randomly split into two groups, **A** and **B**. Each
engineer completes all four tasks, two with each modality:

| Group | Tasks 1–2 | Tasks 3–4 |
|---|---|---|
| **A** | **Baseline** (terminal + logs + re-run) | **Husk** (timeline + modify-and-replay) |
| **B** | **Husk** (timeline + modify-and-replay) | **Baseline** (terminal + logs + re-run) |

Why crossover:
- Every engineer experiences both modalities → individual skill variance is
  controlled (paired T-test on the same person).
- Each task gets timed under both modalities → task-difficulty variance is
  controlled.
- Cross-group balancing removes order effects (learning, fatigue).

Random assignment to A/B is done by a coin flip or hash of email (record
the assignment so the analysis can verify balance).

---

## Per-task workflow

For each (engineer, task) pair:

1. **Warm-up (15–20 min, NOT timed)** — only required once per modality the
   first time the engineer sees it. The engineer resolves a dummy bug under
   the assigned modality to learn the UI / process. **This neutralises the
   familiarity bias against the new tool (Husk).**
2. **Read the task brief** (≤2 min). Confirm understanding.
3. **Start the clock**. Engineer attempts to identify root cause, edit the
   code/prompt/state, verify the fix.
4. **Stop the clock when** the agent produces correct output on the
   `failing_input.json` (the expected fix in the sealed envelope is checked
   to confirm).
5. **Capture**: total minutes, plus three segment timestamps (see below).
6. **Cap**: 60 minutes hard cap per task. If unresolved at 60 min, mark
   `outcome = unresolved` and record `T_total = 60`.

Engineers work in their **own local environment** with **screen recording
on**, sent to the researcher **after** the task (not live). This mitigates
the Hawthorne effect (no live observer pressure).

---

## Timing segments

Each task's wall-clock is decomposed into three segments. The engineer
clicks an in-instrument timer or marks timestamps in `timing_template.csv`:

| Segment | Starts when | Ends when |
|---|---|---|
| `T_identify` | Engineer reads the failure | Engineer states (aloud, on screen recording) "the bug is in node X because Y" |
| `T_edit` | Engineer opens the editor / Monaco | Engineer saves the candidate fix |
| `T_verify` | Engineer triggers the re-run (or replay) | Agent produces correct output |

Total: `T_total = T_identify + T_edit + T_verify`.

Why segment: Husk's leverage is concentrated in `T_identify` (visual
timeline beats log diffing) and `T_verify` (state replay beats full re-run).
`T_edit` should be roughly equal across modalities. Reporting all three
shows where the gain comes from and protects against handwavy total claims.

---

## Statistical analysis

`analysis.py` produces:

1. **Descriptive stats** per modality: mean, stdev, median, p25, p75.
2. **Paired T-test** on `T_total` per (engineer, task-pair under both
   modalities). Requires `task-pair under both modalities` → because of
   crossover, this is achieved across engineers (engineer A1 does T1
   baseline, engineer B1 does T1 Husk → cross-comparison per task).
3. **95 % confidence interval** on the MTTR delta.
4. **Effect size** — Cohen's d.
5. **Box-plot** baseline vs Husk per task + per segment.

The pitch deck reports:
- MTTR mean ± 95 % CI for both modalities.
- p-value of the paired T-test.
- Cohen's d effect size.
- Per-segment breakdown showing where the gain comes from.

**Threshold for publication**: `p < 0.05` AND `effect size d > 0.5` AND
`N ≥ 12`. Below this threshold the study is **inconclusive** and the pitch
falls back to DHV/DCS/MRTT (the SQL hero metrics) without making time
claims.

---

## Mitigated biases

| Bias | Mitigation |
|---|---|
| **Hawthorne effect** (observation alters behaviour) | Screen recording delivered after the fact; no live researcher in the call |
| **Familiarity bias** (new tool disadvantaged by learning curve) | 15–20 min mandatory warm-up per modality before any timed task |
| **Selection bias** (volunteers self-select towards favourable opinion) | Recruit through neutral channels; pre-screen for prior Husk exposure ("Have you used Husk before?" → exclude yes) |
| **Task difficulty variance** | Crossover design — every task is timed under both modalities |
| **Skill variance** | Within-subjects — every engineer is their own control |
| **Order effects** (later tasks faster due to learning) | A/B group assignment alternates the modality order |
| **Demand characteristics** (engineer guesses the expected result) | Don't tell participants which modality is "expected to win"; describe the study as "comparing two debugging workflows" |

---

## Output artefacts

- `results/raw_timings.csv` — one row per (engineer, task, modality), with
  `T_identify`, `T_edit`, `T_verify`, `T_total`, `outcome`.
- `results/analysis.json` — descriptive stats + T-test + CI + Cohen's d.
- `results/plots/` — box plots, per-segment plots, per-task plots.
- `results/REPORT.md` — narrative summary + sample size + caveats. The
  pitch deck cites this report.

---

## Estimated cost & timeline

| Item | Estimate |
|---|---|
| Recruit 15 engineers | 1 week (LinkedIn / Discord outreach + screening) |
| Honorarium | ~€50–100 / engineer = ~€1.000 |
| Sessions | 4 tasks × ~30 min avg × 15 engineers = ~30 h researcher time |
| Analysis + write-up | ~8 h |
| **Total** | **~2 weeks calendar / ~€1.500 + researcher time** |

This is the price of being able to say "MTTR is X minutes ± Y, p < 0.05"
in front of a technical investor. Cheap insurance against the "your numbers
are simulated" rebuttal.
