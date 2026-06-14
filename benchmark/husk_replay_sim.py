"""Husk-assisted MTTR simulator -- ILLUSTRATIVE Monte-Carlo, NOT a hero metric source.

WARNING: this script produces simulated numbers calibrated against expected
per-step latencies of the Husk Studio UI. Its output is suitable for
sanity-checking the order of magnitude, NOT for the pitch deck.

For real, defensible MTTR claims, run the empirical study in
`benchmark/empirical_study/` (within-subjects crossover, paired T-test,
CI 95%). The hero metrics in the pitch come from `metrics.sql`
(DHV / DCS / MRTT) — those are extracted from the live SQLite database.

Measures debug time WITH Husk's replay engine.

Workflow modelled:

    1. Open run in Studio                            ~10 s
    2. Visually identify failing node (timeline)    ~30 s
    3. Click "Modify & replay" → Monaco editor       ~5  s
    4. Edit state JSON (prompt / model / input)      ~90 s
    5. Run from here — re-executes 1–2 nodes only    ~8–14 s wall-time
    6. Read new run, diff vs original                ~30 s

Per debug iteration: ~3–5 minutes. The engineer averages ~3.2 branches before
landing the fix (one model_swap, one prompt_edit, one input_replace + a tail).

The script does NOT actually call the replay API — same Monte-Carlo philosophy
as `baseline_replay.py`. The numbers it produces complement the SQL-extracted
branch counts (`metrics.sql`) and let the case study compute the speed-up
factor directly.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

STEPS: list[tuple[str, float, float]] = [
    ("open_studio", 10 / 60, 2 / 60),       # one-time
    ("identify_node", 30 / 60, 8 / 60),     # one-time
    ("open_monaco", 5 / 60, 1.5 / 60),      # one-time
    ("edit_state", 30 / 60, 10 / 60),       # per branch
    ("replay_partial", 12 / 60, 3 / 60),    # per branch
    ("read_diff", 8 / 60, 2 / 60),          # per branch + final read
]
BRANCHES_MEAN = 3.2
BRANCHES_STDEV = 0.7


def _truncated_normal(rng: random.Random, mu: float, sigma: float, lo: float = 0.0) -> float:
    v = rng.gauss(mu, sigma)
    return max(lo, v)


def simulate_one(rng: random.Random) -> dict:
    branches = max(1, round(_truncated_normal(rng, BRANCHES_MEAN, BRANCHES_STDEV, 1)))
    breakdown: dict[str, float] = {}
    # open_studio / identify_node / open_monaco / read_diff are paid once per
    # failure. edit_state + replay_partial repeat for each branch.
    once = {"open_studio", "identify_node", "open_monaco", "read_diff"}
    for name, mu, sigma in STEPS:
        scale = 1 if name in once else branches
        breakdown[name] = round(_truncated_normal(rng, mu, sigma) * scale, 3)
    breakdown["branches"] = branches
    breakdown["total_min"] = round(
        sum(v for k, v in breakdown.items() if k != "branches"), 3
    )
    return breakdown


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Illustrative Monte-Carlo for Husk-assisted MTTR. "
            "NOT a hero metric source -- see benchmark/empirical_study/ "
            "for the real protocol."
        )
    )
    p.add_argument("-n", "--failures", type=int, default=2_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--out", type=Path, default=Path("benchmark/husk_mttr.jsonl")
    )
    args = p.parse_args()

    rng = random.Random(args.seed)
    samples = [simulate_one(rng) for _ in range(args.failures)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s) + "\n")

    totals = sorted(s["total_min"] for s in samples)
    branches = [s["branches"] for s in samples]
    mean = sum(totals) / len(totals)
    p50 = totals[len(totals) // 2]
    p95 = totals[int(0.95 * len(totals))]
    sigma = math.sqrt(sum((t - mean) ** 2 for t in totals) / len(totals))
    avg_br = sum(branches) / len(branches)

    print(f"Wrote {args.out} ({args.failures} samples, seed={args.seed})")
    print(f"  MTTR mean        = {mean:6.2f} min")
    print(f"  MTTR stdev       = {sigma:6.2f} min")
    print(f"  MTTR p50 / p95   = {p50:6.2f} / {p95:6.2f} min")
    print(f"  avg branches     = {avg_br:6.2f}")
    print(f"  total branches   = {sum(branches)}")
    print(f"  total engineering time = {mean * args.failures / 60:.1f} hours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
