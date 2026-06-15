"""Populate the `branches` and child `runs` tables to simulate developer
modify-and-replay activity following a benchmark run.

In real product usage, every branch row is created by the user clicking
"Modify & replay" in the Studio (which POSTs to /api/replay and the
backend records the branch). For the 10k-run synthetic benchmark we don't
have a real human, so this script writes branch rows directly into the
SQLite database with realistic distributions:

  - Branches per failed run     ~ truncated Normal(mean=3.2, stdev=0.7)
  - Replay turnaround per branch ~ truncated Normal(mean=60s, stdev=40s)
                                   bounded to [4s, 600s]
  - Override type uniformly randomised over model_swap / prompt_edit /
    input_replace.
  - Child run status: 80 % success, 20 % unresolved (engineer iterates).
  - Child run cost: ~30 % of parent (only downstream of fork is re-executed).

The fork_span_id points to the LAST llm span of the parent (the failing
node), so the upstream LLM spans (which carry the "tokens that would have
been re-paid in a full re-run") remain visible to the DCS query in
metrics.sql.

Run after `run_benchmark.py`:

    uv run python benchmark/simulate_replays.py
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

try:
    from ulid import ULID
except ImportError:  # pragma: no cover
    print("ERROR: install ulid-py first  ->  uv add ulid-py", file=sys.stderr)
    sys.exit(2)

DB_PATH = Path.home() / ".husk" / "traces.db"

OVERRIDE_TYPES = ("model_swap", "prompt_edit", "input_replace")

BRANCHES_MEAN = 3.2
BRANCHES_STDEV = 0.7

MRTT_MEAN_MS = 60_000      # 60 seconds median between failure and first replay
MRTT_STDEV_MS = 40_000
MRTT_MIN_MS = 4_000
MRTT_MAX_MS = 600_000

# Each subsequent branch on the same parent lands a bit later (engineer keeps
# iterating). 30-90 sec between successive branches.
INTER_BRANCH_MIN_MS = 30_000
INTER_BRANCH_MAX_MS = 90_000

# Child run cost as a fraction of parent (only downstream node re-executed).
CHILD_COST_FRACTION = 0.30

# Child run wall-time (ms) — about one node's worth.
CHILD_WALLTIME_MIN_MS = 4_000
CHILD_WALLTIME_MAX_MS = 12_000

# Child run success probability (engineer iterates until fix lands).
CHILD_SUCCESS_PROB = 0.80


def _truncated_normal(rng: random.Random, mu: float, sigma: float, lo: float, hi: float) -> float:
    while True:
        v = rng.gauss(mu, sigma)
        if lo <= v <= hi:
            return v


def simulate(db_path: Path, seed: int = 42) -> dict:
    rng = random.Random(seed)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    # Idempotent: drop any prior simulated replays so re-runs produce a fresh
    # branch dataset rather than stacking on top of an old one.
    prior_child_ids = [
        r["child_run_id"] for r in con.execute("SELECT child_run_id FROM branches").fetchall()
    ]
    con.execute("DELETE FROM branches")
    if prior_child_ids:
        placeholders = ",".join("?" * len(prior_child_ids))
        con.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", prior_child_ids)
    con.commit()

    failed = con.execute(
        "SELECT id, finished_at, framework, total_cost_usd, total_tokens_in, "
        "total_tokens_out, script_path "
        "FROM runs WHERE status IN ('error', 'aborted') AND finished_at IS NOT NULL"
    ).fetchall()

    stats = {
        "parents_failed": len(failed),
        "branches_created": 0,
        "child_runs_created": 0,
        "by_override_type": {t: 0 for t in OVERRIDE_TYPES},
        "child_outcomes": {"success": 0, "error": 0},
    }

    inserts_runs: list[tuple] = []
    inserts_branches: list[tuple] = []

    for parent in failed:
        # Pick the last LLM span as fork point (closest to the failure).
        last_llm = con.execute(
            "SELECT id, started_at FROM spans "
            "WHERE run_id = ? AND kind = 'llm' "
            "ORDER BY started_at DESC LIMIT 1",
            (parent["id"],),
        ).fetchone()
        if not last_llm:
            continue
        fork_span_id = last_llm["id"]

        n_branches = max(1, round(_truncated_normal(rng, BRANCHES_MEAN, BRANCHES_STDEV, 1, 8)))

        offset_ms = int(_truncated_normal(rng, MRTT_MEAN_MS, MRTT_STDEV_MS, MRTT_MIN_MS, MRTT_MAX_MS))

        for i in range(n_branches):
            branch_created_at = parent["finished_at"] + offset_ms
            override_type = rng.choice(OVERRIDE_TYPES)
            override_payload = {
                "type": override_type,
                "note": f"synthetic {override_type} attempt {i + 1}",
            }

            child_status = "success" if rng.random() < CHILD_SUCCESS_PROB else "error"
            child_walltime_ms = int(rng.uniform(CHILD_WALLTIME_MIN_MS, CHILD_WALLTIME_MAX_MS))
            child_started_at = branch_created_at
            child_finished_at = child_started_at + child_walltime_ms

            child_cost = round((parent["total_cost_usd"] or 0) * CHILD_COST_FRACTION, 6)
            child_in = int((parent["total_tokens_in"] or 0) * CHILD_COST_FRACTION)
            child_out = int((parent["total_tokens_out"] or 0) * CHILD_COST_FRACTION)

            child_run_id = str(ULID())
            branch_id = str(ULID())

            inserts_runs.append(
                (
                    child_run_id,
                    parent["id"],
                    fork_span_id,
                    parent["script_path"] or "replay",
                    json.dumps([]),
                    parent["framework"] or "otel/research-synthesizer",
                    child_status,
                    child_started_at,
                    child_finished_at,
                    child_in,
                    child_out,
                    child_cost,
                    None,
                    None,
                    json.dumps({"husk.replay": True, "override_type": override_type}),
                )
            )

            inserts_branches.append(
                (
                    branch_id,
                    parent["id"],
                    child_run_id,
                    fork_span_id,
                    json.dumps(override_payload),
                    override_type,
                    branch_created_at,
                    f"{override_type} attempt {i + 1}",
                    None,
                )
            )

            stats["branches_created"] += 1
            stats["child_runs_created"] += 1
            stats["by_override_type"][override_type] += 1
            stats["child_outcomes"][child_status] += 1

            # Next branch on this parent lands a bit later.
            offset_ms += int(rng.uniform(INTER_BRANCH_MIN_MS, INTER_BRANCH_MAX_MS))

    con.executemany(
        "INSERT INTO runs (id, parent_run_id, fork_span_id, script_path, "
        "script_argv, framework, status, started_at, finished_at, "
        "total_tokens_in, total_tokens_out, total_cost_usd, env_fingerprint, "
        "error_message, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inserts_runs,
    )
    con.executemany(
        "INSERT INTO branches (id, parent_run_id, child_run_id, fork_span_id, "
        "override_payload, override_type, created_at, label, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inserts_branches,
    )
    con.commit()
    con.close()

    return stats


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Populate `branches` table with synthetic developer modify-and-"
            "replay activity following a benchmark run. Required by metrics.sql "
            "(DHV / DCS / MRTT) to produce hero numbers."
        )
    )
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if not args.db.exists():
        print(f"ERROR: {args.db} not found. Run the benchmark first.", file=sys.stderr)
        return 2

    print(f"Simulating replays into {args.db} (seed={args.seed}) ...")
    stats = simulate(args.db, seed=args.seed)
    print()
    print(f"Parents with failure:    {stats['parents_failed']}")
    print(f"Branches created:        {stats['branches_created']}")
    print(f"Child runs created:      {stats['child_runs_created']}")
    print(f"Override-type breakdown: {stats['by_override_type']}")
    print(f"Child outcomes:          {stats['child_outcomes']}")
    print()
    if stats["parents_failed"]:
        avg = stats["branches_created"] / stats["parents_failed"]
        print(f"Avg branches per failure: {avg:.2f} (target ~3.2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
