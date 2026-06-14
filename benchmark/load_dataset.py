"""Download N queries from a real-world academic QA dataset and cache them
as JSONL for the benchmark.

Default: TriviaQA RC (no-context) validation split, fetched via the public
HuggingFace datasets-server (no `datasets` package required, just stdlib).

Why TriviaQA: real human-authored questions, ACL 2017, widely cited, light
to download (we fetch JSON pages, not the full archive). Citing it in the
pitch ('benchmark eseguito su query del TriviaQA dataset, Allen AI, ACL
2017') is far more credible than synthetic topics.

Output: each row in benchmark/queries_500.jsonl has the shape:
    {"index": 0, "topic": "Who was the man behind The Chipmunks?",
     "expected_answer": "David Seville", "source": "triviaqa:tc_2"}
The benchmark runner reads `topic` as the input to the research agent.

Usage:
    uv run python benchmark/load_dataset.py --source triviaqa --n 500
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT_DEFAULT = Path("benchmark/queries_500.jsonl")
PAGE_SIZE = 100

SOURCES = {
    "triviaqa": {
        "dataset": "mandarjoshi/trivia_qa",
        "config": "rc.nocontext",
        "split": "validation",
        "answer_path": ("answer", "value"),
        "question_path": ("question",),
        "id_path": ("question_id",),
    },
    "squad2": {
        "dataset": "rajpurkar/squad_v2",
        "config": "squad_v2",
        "split": "validation",
        "answer_path": ("answers", "text"),  # list, take first
        "question_path": ("question",),
        "id_path": ("id",),
    },
    "nq": {
        "dataset": "google-research-datasets/natural_questions",
        "config": "default",
        "split": "validation",
        "answer_path": ("annotations", "short_answers"),
        "question_path": ("question", "text"),
        "id_path": ("id",),
    },
}


def _deep_get(d: dict, path: tuple) -> object:
    cur = d
    for k in path:
        if cur is None:
            return None
        if isinstance(cur, list):
            cur = cur[0] if cur else None
            if cur is None:
                return None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def fetch_page(dataset: str, config: str, split: str, offset: int, length: int) -> list[dict]:
    qs = (
        f"dataset={urllib.parse.quote(dataset, safe='')}"
        f"&config={urllib.parse.quote(config, safe='')}"
        f"&split={split}&offset={offset}&length={length}"
    )
    url = f"https://datasets-server.huggingface.co/rows?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "husk-benchmark/0.1"})
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            return data.get("rows", [])
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"HF datasets-server failed after 3 retries: {last_err}")


def load(source: str, n: int, out: Path) -> int:
    if source not in SOURCES:
        print(f"ERROR: unknown source {source}. Options: {list(SOURCES)}", file=sys.stderr)
        return 2

    spec = SOURCES[source]
    written = 0
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as fh:
        offset = 0
        while written < n:
            page = fetch_page(
                spec["dataset"], spec["config"], spec["split"], offset, PAGE_SIZE
            )
            if not page:
                print(f"WARN: empty page at offset={offset}, stopping early.", file=sys.stderr)
                break
            for row_wrap in page:
                if written >= n:
                    break
                row = row_wrap.get("row", {})
                question = _deep_get(row, spec["question_path"])
                answer = _deep_get(row, spec["answer_path"])
                qid = _deep_get(row, spec["id_path"]) or f"{source}-{offset + written}"

                if not question or not isinstance(question, str):
                    continue
                question = question.strip()
                if len(question) < 8 or len(question) > 300:
                    continue
                if answer is not None and not isinstance(answer, str):
                    # squad takes first answer text; nq is more complex, skip if odd
                    try:
                        answer = str(answer)
                    except (TypeError, ValueError):
                        answer = None

                fh.write(
                    json.dumps(
                        {
                            "index": written,
                            "topic": question,
                            "expected_answer": answer,
                            "source": f"{source}:{qid}",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1
            offset += PAGE_SIZE
            # Be gentle with the public endpoint.
            time.sleep(0.3)
    return written


def main() -> int:
    p = argparse.ArgumentParser(description="Download QA queries for the Husk benchmark.")
    p.add_argument("--source", default="triviaqa", choices=list(SOURCES))
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = p.parse_args()

    print(f"Downloading {args.n} queries from {args.source} -> {args.out} ...")
    written = load(args.source, args.n, args.out)
    print(f"Wrote {written} rows.")
    if written < args.n:
        print(f"WARN: requested {args.n}, only got {written}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
