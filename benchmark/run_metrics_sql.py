"""Run benchmark/metrics.sql against ~/.husk/traces.db and pretty-print the
results. Works around the lack of a `sqlite3` CLI on Windows by using the
sqlite3 module that ships with Python (which uv already provides).

Usage:
    uv run python benchmark/run_metrics_sql.py
    uv run python benchmark/run_metrics_sql.py --out benchmark/results.txt
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path


def split_statements(sql: str) -> list[str]:
    # Strip line comments and dot-commands (SQLite CLI specific, not SQL).
    lines = []
    for raw in sql.splitlines():
        s = raw.strip()
        if s.startswith("--"):
            continue
        if s.startswith("."):
            continue
        lines.append(raw)
    text = "\n".join(lines)

    # Split on `;` but respect parentheses / quoted strings (good-enough).
    statements: list[str] = []
    depth = 0
    in_quote: str | None = None
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if in_quote:
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ("'", '"'):
            in_quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            statements.append("".join(buf).strip().rstrip(";").strip())
            buf = []
    if buf and "".join(buf).strip():
        statements.append("".join(buf).strip())
    return [s for s in statements if s]


def render_row(headers: list[str], row: tuple) -> str:
    parts = []
    for h, v in zip(headers, row, strict=False):
        if v is None:
            vs = "—"
        elif isinstance(v, float):
            vs = f"{v:.4f}"
        else:
            vs = str(v)
        parts.append(f"{h}={vs}")
    return "  ".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=Path.home() / ".husk" / "traces.db")
    p.add_argument("--sql", type=Path, default=Path("benchmark/metrics.sql"))
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    if not args.db.exists():
        print(f"ERROR: {args.db} not found. Run the benchmark first.", file=sys.stderr)
        return 2
    if not args.sql.exists():
        print(f"ERROR: {args.sql} not found.", file=sys.stderr)
        return 2

    sql = args.sql.read_text(encoding="utf-8")
    statements = split_statements(sql)

    con = sqlite3.connect(str(args.db))
    out_lines: list[str] = []

    def emit(line: str = "") -> None:
        out_lines.append(line)
        # ASCII-safe stdout for Windows console (cp1252).
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"))

    emit(f"# Husk benchmark metrics — extracted {len(statements)} SQL statements")
    emit(f"# DB: {args.db}")
    emit("")

    for stmt in statements:
        try:
            cur = con.execute(stmt)
        except sqlite3.Error as e:
            emit(f"!! SQL ERROR on:\n{stmt}\n   {e}\n")
            continue
        if cur.description is None:
            continue
        headers = [c[0] for c in cur.description]
        rows = cur.fetchall()
        # If this is a banner SELECT (single string column whose row looks like
        # a banner), render as a heading and continue.
        if len(headers) == 1 and rows and isinstance(rows[0][0], str) and re.search(r"[═─]", rows[0][0]):
            emit("")
            emit(rows[0][0])
            continue
        if not rows:
            emit("  (no rows)")
            continue
        for row in rows:
            emit("  " + render_row(headers, row))

    con.close()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(out_lines), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
