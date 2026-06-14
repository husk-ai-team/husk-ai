"""Baseline MTTR simulator -- ILLUSTRATIVE Monte-Carlo, NOT a hero metric source.

WARNING: this script produces simulated numbers calibrated against anecdotal
engineering reports. Its output is suitable for "what range of debug times
would Husk plausibly affect?" exploration, NOT for the pitch deck.

The defensible hero metrics come from `hero_report.py` (D1–D5 over the live
SQLite trace DB), not from this simulator.

Measures debug time WITHOUT Husk.

We assume an engineer faced with a failed run goes through this workflow:

    1. Read stdout / log file                       ~7  min
    2. Identify failing node (which step broke?)   ~7  min
    3. Edit code / prompt                           ~5  min
    4. Re-run the FULL graph (no checkpoint reuse)  ~24 s wall-time
       + ~10 min of context-switch / wait
    5. Iterate 2–3 times                            multiplier ~2.5x

Net: ~32 min per failure on average. We model this with a parametric noise
distribution and emit a CSV with per-failure timings so the case-study can
report mean / p50 / p95.

The script does NOT actually invoke any LLM — it's a Monte-Carlo simulation
of human debug time. The point is to establish the apples-to-apples baseline
that the Husk replay path is compared against.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

# Per-step minute distributions (mean, stdev) — calibrated to land at a ~32
# min total mean MTTR per failure, consistent with anecdotal engineering
# reports on multi-step agent pipelines.
STEPS: list[tuple[str, float, float]] = [
    ("read_logs", 6.0, 2.0),       # one-time
    ("identify_node", 5.0, 2.0),   # one-time
    ("edit_code", 4.0, 1.5),       # one-time
    ("rerun_full_graph", 0.5, 0.1),  # per iteration (~24s wall-time + flush)
    ("context_switch", 6.0, 2.0),  # per iteration
]
ITERATIONS_MEAN = 2.5
ITERATIONS_STDEV = 0.8


def _truncated_normal(rng: random.Random, mu: float, sigma: float, lo: float = 0.0) -> float:
    """Draw from N(mu, sigma) clipped at `lo`."""
    v = rng.gauss(mu, sigma)
    return max(lo, v)


def simulate_one(rng: random.Random) -> dict:
    """One synthetic debug session. Returns per-step minutes + total."""
    iters = max(1, round(_truncated_normal(rng, ITERATIONS_MEAN, ITERATIONS_STDEV, 1)))
    breakdown: dict[str, float] = {}
    for name, mu, sigma in STEPS:
        # Steps 4 and 5 (rerun + context switch) scale with iterations,
        # the analysis ones (1, 2, 3) are paid once.
        scale = iters if name in {"rerun_full_graph", "context_switch"} else 1
        breakdown[name] = round(_truncated_normal(rng, mu, sigma) * scale, 2)
    breakdown["iterations"] = iters
    breakdown["total_min"] = round(sum(v for k, v in breakdown.items() if k != "iterations"), 2)
    return breakdown


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Illustrative Monte-Carlo for baseline MTTR (no Husk). "
            "NOT a hero metric source -- the hero metrics come from hero_report.py."
        )
    )
    p.add_argument(
        "-n",
        "--failures",
        type=int,
        default=2_000,
        help="Number of failures to simulate (default: 2000, the 20%% of 10k).",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--out", type=Path, default=Path("benchmark/baseline_mttr.jsonl")
    )
    args = p.parse_args()

    rng = random.Random(args.seed)
    samples = [simulate_one(rng) for _ in range(args.failures)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s) + "\n")

    totals = sorted(s["total_min"] for s in samples)
    mean = sum(totals) / len(totals)
    p50 = totals[len(totals) // 2]
    p95 = totals[int(0.95 * len(totals))]
    sigma = math.sqrt(sum((t - mean) ** 2 for t in totals) / len(totals))

    print(f"Wrote {args.out} ({args.failures} samples, seed={args.seed})")
    print(f"  mean  = {mean:6.2f} min")
    print(f"  stdev = {sigma:6.2f} min")
    print(f"  p50   = {p50:6.2f} min")
    print(f"  p95   = {p95:6.2f} min")
    print(f"  total engineering time = {mean * args.failures / 60:.1f} hours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
