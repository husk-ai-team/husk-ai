-- benchmark/metrics.sql
--
-- Query suite that extracts every hero and supporting metric for the Husk
-- case study directly from the local SQLite at ~/.husk/traces.db.
--
-- Run from the repo root:
--   sqlite3 ~/.husk/traces.db < benchmark/metrics.sql
--
-- All numbers come from COUNT / SUM / aggregation on tables actually populated
-- by the benchmark run. Nothing here is simulated or Monte-Carlo-extrapolated.
--
-- ═══════════════════════════════════════════════════════════════════════════
-- HERO METRICS (the three numbers the pitch deck lands)
--   • DHV  — Developer Hypothesis Velocity   (section H1)
--   • DCS  — Deterministic Context Savings   (section H2)
--   • MRTT — Median Replay Turnaround Time   (section H3)
--
-- SUPPORTING METRICS (volume, distribution, latency) follow in sections S1-S7.
-- ═══════════════════════════════════════════════════════════════════════════

.headers on
.mode column
.nullvalue —

-- ─────────────────────────────────────────────────────────────────────────
-- H1. DHV — Developer Hypothesis Velocity
-- ─────────────────────────────────────────────────────────────────────────
-- "How many corrective hypotheses does an engineer test per failed run?"
-- Without Husk, the realistic baseline is ~1 retry (full re-run is expensive).
-- With Husk, branches are cheap → engineers explore multiple what-ifs.
SELECT '═══ H1 · DHV — Developer Hypothesis Velocity ═══' AS hero_metric;

WITH per_parent AS (
    SELECT
        parent_run_id,
        COUNT(*) AS branch_count
    FROM branches
    GROUP BY parent_run_id
)
SELECT
    ROUND(AVG(branch_count), 2)                                       AS dhv_avg_branches_per_failure,
    COUNT(*)                                                          AS failed_runs_explored,
    SUM(branch_count)                                                 AS total_hypotheses_tested,
    MIN(branch_count)                                                 AS min_branches_per_failure,
    MAX(branch_count)                                                 AS max_branches_per_failure
FROM per_parent;

-- Override-type fanout: which kind of "what-if" do engineers test?
SELECT '── H1b · Override-type breakdown ──' AS section;

SELECT
    override_type,
    COUNT(*)                                                          AS branches,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM branches), 2)      AS pct
FROM branches
GROUP BY override_type
ORDER BY branches DESC;

-- ─────────────────────────────────────────────────────────────────────────
-- H2. DCS — Deterministic Context Savings
-- ─────────────────────────────────────────────────────────────────────────
-- "How many tokens and USD does the modify-and-replay mechanism save by
--  bypassing upstream nodes that don't need re-execution?"
--
-- For each branch, the upstream span tokens are tokens that would have been
-- re-paid if the engineer had re-run the full graph instead of using Husk's
-- state replay. We measure the tokens at all spans of the parent run whose
-- started_at is <= the fork span's started_at (i.e. nodes BEFORE the branch
-- point). Those tokens are saved on every replay.
SELECT '═══ H2 · DCS — Deterministic Context Savings ═══' AS hero_metric;

WITH fork_points AS (
    SELECT
        b.id                  AS branch_id,
        b.parent_run_id,
        b.fork_span_id,
        fork.started_at       AS fork_started_at
    FROM branches b
    JOIN spans fork ON fork.id = b.fork_span_id
),
upstream_spans AS (
    -- All LLM spans in the parent run that happened at or before the fork.
    SELECT
        fp.branch_id,
        s.tokens_in,
        s.tokens_out,
        s.cost_usd
    FROM fork_points fp
    JOIN spans s
      ON s.run_id = fp.parent_run_id
     AND s.started_at <= fp.fork_started_at
     AND s.kind = 'llm'
)
SELECT
    SUM(tokens_in + tokens_out)                                       AS dcs_tokens_saved_total,
    ROUND(SUM(cost_usd), 4)                                           AS dcs_usd_saved_total,
    ROUND(AVG(tokens_in + tokens_out), 2)                             AS avg_tokens_saved_per_branch,
    ROUND(AVG(cost_usd), 6)                                           AS avg_usd_saved_per_branch
FROM upstream_spans;

-- ─────────────────────────────────────────────────────────────────────────
-- H3. MRTT — Median Replay Turnaround Time
-- ─────────────────────────────────────────────────────────────────────────
-- "After a failure, how fast does the first corrective replay land?"
-- We measure the wall-clock interval between parent_run.finished_at and
-- branch.created_at. SQLite lacks PERCENTILE_CONT, so we compute via NTILE
-- on the ordered set, picking the central value.
SELECT '═══ H3 · MRTT — Median Replay Turnaround Time ═══' AS hero_metric;

WITH turnarounds AS (
    SELECT
        (b.created_at - p.finished_at) AS turnaround_ms
    FROM branches b
    JOIN runs p ON p.id = b.parent_run_id
    WHERE p.status IN ('error', 'aborted')
      AND p.finished_at IS NOT NULL
),
ranked AS (
    SELECT
        turnaround_ms,
        ROW_NUMBER() OVER (ORDER BY turnaround_ms) AS rn,
        COUNT(*) OVER () AS cnt
    FROM turnarounds
)
SELECT
    (SELECT ROUND(turnaround_ms, 0) FROM ranked WHERE rn = (cnt + 1) / 2)
                                                                      AS mrtt_p50_ms,
    (SELECT ROUND(turnaround_ms, 0) FROM ranked WHERE rn = CAST(0.95 * cnt AS INTEGER))
                                                                      AS mrtt_p95_ms,
    (SELECT MIN(turnaround_ms) FROM turnarounds)                      AS mrtt_min_ms,
    (SELECT MAX(turnaround_ms) FROM turnarounds)                      AS mrtt_max_ms,
    (SELECT ROUND(AVG(turnaround_ms), 0) FROM turnarounds)            AS mrtt_mean_ms,
    (SELECT COUNT(*) FROM turnarounds)                                AS samples;

-- ═════════════════════════════════════════════════════════════════════════
-- SUPPORTING METRICS — volume / distribution / latency
-- ═════════════════════════════════════════════════════════════════════════

-- S1. Volume
SELECT '── S1 · Volume ──' AS section;
SELECT
    (SELECT COUNT(*) FROM runs)                                       AS total_runs,
    (SELECT COUNT(*) FROM spans)                                      AS total_spans,
    (SELECT COUNT(*) FROM branches)                                   AS total_branches,
    (SELECT COUNT(*) FROM spans WHERE kind = 'llm')                   AS llm_spans,
    (SELECT COUNT(*) FROM spans WHERE kind = 'tool')                  AS tool_spans;

-- S2. Outcome distribution
SELECT '── S2 · Outcome distribution ──' AS section;
SELECT
    status,
    COUNT(*)                                                          AS runs,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM runs), 2)          AS pct
FROM runs
GROUP BY status
ORDER BY runs DESC;

-- S2b. Failure breakdown by injected mode
-- The benchmark sets `benchmark.failure_mode` as an OTel attribute on the
-- root agent.run span, so we read it from spans.attrs (JSON) for runs whose
-- root span carries the marker.
SELECT '── S2b · Failures by injected mode ──' AS section;
SELECT
    json_extract(s.attrs, '$."benchmark.failure_mode"')               AS failure_mode,
    COUNT(DISTINCT s.run_id)                                          AS runs
FROM spans s
JOIN runs r ON r.id = s.run_id
WHERE r.status = 'error'
  AND json_extract(s.attrs, '$."benchmark.failure_mode"') IS NOT NULL
GROUP BY failure_mode
ORDER BY runs DESC;

-- S3. % failures with at least one corrective replay
SELECT '── S3 · % failures with ≥1 replay ──' AS section;
SELECT
    ROUND(
        100.0 *
        (SELECT COUNT(DISTINCT b.parent_run_id)
           FROM branches b JOIN runs r ON r.id = b.parent_run_id
          WHERE r.status = 'error')
        /
        NULLIF((SELECT COUNT(*) FROM runs WHERE status = 'error'), 0),
    2)                                                                AS pct_failed_with_replay;

-- S4. Cost & tokens — overall
SELECT '── S4 · Cost & tokens (overall) ──' AS section;
SELECT
    ROUND(SUM(total_cost_usd), 4)                                     AS total_cost_usd,
    SUM(total_tokens_in)                                              AS total_tokens_in,
    SUM(total_tokens_out)                                             AS total_tokens_out,
    ROUND(AVG(total_cost_usd), 6)                                     AS avg_run_cost_usd
FROM runs;

-- S5. Run wall-time distribution
SELECT '── S5 · Run duration (ms) ──' AS section;
SELECT
    ROUND(AVG(finished_at - started_at), 0)                           AS avg_ms,
    MIN(finished_at - started_at)                                     AS min_ms,
    MAX(finished_at - started_at)                                     AS max_ms
FROM runs
WHERE finished_at IS NOT NULL;

-- S5b. Per-node mean latency
SELECT '── S5b · Per-node mean latency (ms) ──' AS section;
SELECT
    name,
    COUNT(*)                                                          AS spans,
    ROUND(AVG(finished_at - started_at), 0)                           AS avg_ms
FROM spans
WHERE finished_at IS NOT NULL
  AND kind IN ('llm', 'tool', 'chain')
GROUP BY name
ORDER BY avg_ms DESC;

-- S6. Framework distribution
SELECT '── S6 · By framework ──' AS section;
SELECT framework, COUNT(*) AS runs
FROM runs
GROUP BY framework
ORDER BY runs DESC;

-- S6b. Model distribution
SELECT '── S6b · By model ──' AS section;
SELECT
    model,
    COUNT(*)                                                          AS spans,
    SUM(tokens_in)                                                    AS tokens_in,
    SUM(tokens_out)                                                   AS tokens_out,
    ROUND(SUM(cost_usd), 4)                                           AS cost_usd
FROM spans
WHERE model IS NOT NULL
GROUP BY model
ORDER BY cost_usd DESC;
