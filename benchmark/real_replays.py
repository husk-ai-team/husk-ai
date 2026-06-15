"""Trigger REAL replays for every failed parent run in the benchmark, and
record each as a row in the `branches` table.

We call the same `replay_graph` engine that Husk's /api/replay endpoint uses,
but in-process from this CLI so that the provider API key (set as an env var
here) is visible to the re-imported graph module. The child run's
LLM calls hit Groq for real; the spans land in ~/.husk/traces.db via the
agent's OTel exporter (the same backend the parent runs went to).

After each successful replay we INSERT into `branches` linking parent_run_id
to the child's run_id, with override_type recorded honestly (one branch per
failure → DHV = 1.0).

Usage:
    $env:GROQ_API_KEY = '<key>'
    uv run python benchmark/real_replays.py [--since TS] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

try:
    from ulid import ULID
except ImportError:  # pragma: no cover
    print("ERROR: install ulid-py first  ->  uv add ulid-py", file=sys.stderr)
    sys.exit(2)

# Match the parents' timing mode so the wall-time speed-up (D1) is a clean
# apples-to-apples ratio: parents run with BENCH_FAST=1 (node sleeps off →
# wall-time = real LLM-API latency), so replays must too. Set before the graph
# module is imported (lazily, inside replay_graph). setdefault respects an
# explicit override.
os.environ.setdefault("BENCH_FAST", "1")

DB_PATH = Path.home() / ".husk" / "traces.db"

OVERRIDE_BY_MODE = {
    "N1": ("input_replace", "Cleaner topic phrasing for query expansion"),
    "N2": ("input_replace", "Broader retrieval scope"),
    "N3": ("prompt_edit", "Synthesize: cite only listed source numbers"),
    "N4": ("prompt_edit", "Cite-check: strict mismatch detection"),
}

# Which node the replay should resume from (re-run) for each failure mode. This
# is the FAILING node, so the fix re-runs it and everything downstream. It must
# come from the injected failure mode, NOT the "last LLM span" heuristic: for N2
# the last LLM span is `synthesize`, but the failure is in `retrieve`, so forking
# at synthesize would never re-run retrieval and `sources` would stay empty.
FORK_NODE_BY_MODE = {
    "N1": "query_expansion",
    "N2": "retrieve",
    "N3": "synthesize",
    "N4": "cite_check",
}


def _recover_topic(con: sqlite3.Connection, run_id: str) -> str:
    row = con.execute(
        "SELECT input_inline FROM spans "
        "WHERE run_id = ? AND name = 'query_expansion' LIMIT 1",
        (run_id,),
    ).fetchone()
    if row:
        try:
            inline = row[0]
            if isinstance(inline, str):
                inline = json.loads(inline)
            if isinstance(inline, dict):
                topic = inline.get("topic")
                if isinstance(topic, str):
                    return topic
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    return "Replay (topic not recoverable)"


def _find_graph_module(con: sqlite3.Connection, run_id: str) -> str | None:
    """Look up the husk.graph_module attribute from the run's root span."""
    row = con.execute(
        "SELECT json_extract(s.attrs, '$.\"husk.graph_module\"') "
        "FROM spans s WHERE s.run_id = ? AND s.name = 'agent.run' LIMIT 1",
        (run_id,),
    ).fetchone()
    return row[0] if row and row[0] else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument(
        "--since", type=int, default=0,
        help="Only consider parent runs started after this UNIX-ms timestamp",
    )
    p.add_argument(
        "--limit", type=int, default=500,
        help="Cap number of replays issued",
    )
    p.add_argument(
        "--sleep-ms", type=int, default=200,
        help="Pause between replays to respect Groq rate limit",
    )
    args = p.parse_args()

    if not args.db.exists():
        print(f"ERROR: {args.db} not found.", file=sys.stderr)
        return 2
    if not (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("CEREBRAS_API_KEY")
        or os.environ.get("GROQ_API_KEY")
    ):
        print(
            "ERROR: no LLM key set (OPENROUTER_API_KEY / CEREBRAS_API_KEY / GROQ_API_KEY).",
            file=sys.stderr,
        )
        return 2

    # Import the Husk replay engine (lives in the backend package).
    try:
        from husk_studio_backend.replay.graph_replay import replay_graph
    except ImportError as e:
        print(f"ERROR: replay engine unavailable: {e}", file=sys.stderr)
        return 2

    con = sqlite3.connect(str(args.db))
    con.row_factory = sqlite3.Row

    failed = con.execute(
        """
        SELECT r.id AS run_id, r.framework, r.total_cost_usd,
               r.total_tokens_in, r.total_tokens_out
        FROM runs r
        WHERE r.parent_run_id IS NULL
          AND r.status IN ('error', 'aborted')
          AND r.started_at >= ?
        ORDER BY r.started_at
        LIMIT ?
        """,
        (args.since, args.limit),
    ).fetchall()

    if not failed:
        print(
            f"No failed runs with started_at >= {args.since} (limit {args.limit}).",
            file=sys.stderr,
        )
        return 1

    print(f"Replaying {len(failed)} failed runs (in-process, real Groq) ...")

    n_ok = 0
    n_err = 0
    for parent in failed:
        # Recover the failure_mode from the root agent.run span attrs.
        root = con.execute(
            "SELECT id, attrs FROM spans "
            "WHERE run_id = ? AND name = 'agent.run' LIMIT 1",
            (parent["run_id"],),
        ).fetchone()
        failure_mode = None
        parent_thread_id = None
        if root is not None:
            try:
                attrs = (
                    json.loads(root["attrs"])
                    if isinstance(root["attrs"], str)
                    else (root["attrs"] or {})
                )
            except json.JSONDecodeError:
                attrs = {}
            failure_mode = attrs.get("benchmark.failure_mode")
            parent_thread_id = attrs.get("husk.thread_id")

        # Pick the last LLM span as fork point (closest to the failure).
        last_llm = con.execute(
            "SELECT id FROM spans "
            "WHERE run_id = ? AND kind = 'llm' "
            "ORDER BY started_at DESC LIMIT 1",
            (parent["run_id"],),
        ).fetchone()
        if last_llm is None:
            n_err += 1
            print(f"  [skip] {parent['run_id'][:10]}: no LLM span")
            continue
        fork_span_id = last_llm["id"]

        graph_module = _find_graph_module(con, parent["run_id"])
        if not graph_module:
            n_err += 1
            print(f"  [skip] {parent['run_id'][:10]}: no husk.graph_module attr")
            continue

        override_type, label = OVERRIDE_BY_MODE.get(
            failure_mode or "", ("prompt_edit", "Generic replay attempt")
        )
        # Resume from the failing node (re-run it + downstream). Derived from the
        # injected mode, not the last-LLM-span heuristic (see FORK_NODE_BY_MODE).
        fork_node = FORK_NODE_BY_MODE.get(failure_mode or "")

        topic = _recover_topic(con, parent["run_id"])
        state_override = {
            "topic": topic,
            "failure_mode": None,  # don't re-inject the failure
        }

        try:
            t0 = time.time()
            # When parent_thread_id + fork_node are known, replay_graph does a
            # true checkpoint resume (bypassing upstream nodes). Otherwise it
            # falls back to a full re-run with a fresh thread.
            result = replay_graph(
                graph_module=graph_module,
                state_override=state_override,
                parent_thread_id=parent_thread_id,
                fork_node=fork_node,
            )
            child_thread_id = result.get("thread_id")
            child_id = result.get("child_id")

            # The child run lands in the DB via OTel ingest. Wait briefly, then
            # locate it. A checkpoint resume reuses the parent's thread_id, so we
            # match on the unique husk.replay.child_id marker when present, and
            # fall back to thread_id for the legacy full-re-run path.
            child_run_id = None
            for _ in range(10):
                time.sleep(0.3)
                if child_id:
                    row = con.execute(
                        "SELECT s.run_id FROM spans s WHERE s.name = 'agent.run' "
                        "  AND json_extract(s.attrs, "
                        "'$.\"husk.replay.child_id\"') = ?",
                        (child_id,),
                    ).fetchone()
                else:
                    row = con.execute(
                        "SELECT s.run_id FROM spans s "
                        "WHERE s.name = 'agent.run' AND s.started_at >= ? "
                        "  AND json_extract(s.attrs, "
                        "'$.\"husk.thread_id\"') = ?",
                        (int(t0 * 1000) - 5000, child_thread_id),
                    ).fetchone()
                if row:
                    child_run_id = row[0]
                    break
            if child_run_id is None:
                n_err += 1
                print(
                    f"  [partial] {parent['run_id'][:10]}: replay ran but "
                    f"child not in DB yet (child_id={child_id or child_thread_id})"
                )
                continue

            con.execute(
                "INSERT INTO branches (id, parent_run_id, child_run_id, "
                "fork_span_id, override_payload, override_type, created_at, "
                "label, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(ULID()),
                    parent["run_id"],
                    child_run_id,
                    fork_span_id,
                    json.dumps({"type": override_type, "label": label}),
                    override_type,
                    int(time.time() * 1000),
                    label,
                    None,
                ),
            )
            con.commit()
            n_ok += 1
            if n_ok % 5 == 0:
                print(f"  [{n_ok}/{len(failed)}] last={parent['run_id'][:10]} ok")
        except Exception as e:  # noqa: BLE001
            n_err += 1
            print(f"  [err] {parent['run_id'][:10]}: {type(e).__name__}: {e}")

        time.sleep(args.sleep_ms / 1000.0)

    con.close()
    print(f"Done: {n_ok} branches created, {n_err} errors.")
    return 0 if n_ok else 1


if __name__ == "__main__":
    sys.exit(main())
