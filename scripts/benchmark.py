"""Score the matcher against synthetic cases with known answers.

    python scripts/benchmark.py --seeds 101-110 --out benchmark.json

The matcher thresholds were tuned on seeds 1 to 3. Report numbers from other seeds.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from darnleaf import imaging, pipeline, sample


def kind(page: int | None) -> str:
    if page is None:
        return "not in booklet"
    if page == 2:
        return "blank"
    if 30 <= page <= 35:
        return "repeated form"
    return "figure" if page % 11 == 0 else "text"


def parse_seeds(text: str) -> list[int]:
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def run_case(seed: int, pages: int, use_ocr: bool) -> list[dict]:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp)
        truth = sample.make_case(case, pages=pages, seed=seed)
        turned = json.loads((case / "truth.json").read_text())["turned_ccw"]
        sources = imaging.expand_sources(sorted((case / "rescans").glob("*.jpg")))
        proposals = pipeline.run(case / "original.pdf", sources, use_ocr=use_ocr)
        for source, proposal in zip(sources, proposals, strict=True):
            answer = truth[source.label]
            chosen = None if proposal.page is None else proposal.page + 1
            listed = [c.page + 1 for c in proposal.candidates]
            rows.append(
                {
                    "seed": seed,
                    "kind": kind(answer),
                    "status": proposal.status,
                    "correct": chosen == answer,
                    "in_candidates": answer in listed if answer else proposal.page is None,
                    "turn_ok": proposal.page is None or chosen != answer or proposal.candidates[0].quarter_turns == (turned.get(source.label, 0) // 90) % 4,
                }
            )
    return rows


def summarise(rows: list[dict]) -> dict:
    out = {"rescans": len(rows), "by_kind": {}}
    for label in ["text", "figure", "repeated form", "blank", "not in booklet", "all"]:
        sel = rows if label == "all" else [r for r in rows if r["kind"] == label]
        if not sel:
            continue
        statuses = Counter(r["status"] for r in sel)
        clear = [r for r in sel if r["status"] == "clear"]
        out["by_kind"][label] = {
            "n": len(sel),
            "top1": round(sum(r["correct"] for r in sel) / len(sel), 3),
            "listed": round(sum(r["in_candidates"] for r in sel) / len(sel), 3),
            "clear": statuses["clear"],
            "check": statuses["check"],
            "none": statuses["none"],
            "clear_wrong": sum(not r["correct"] for r in clear),
            "turn_ok": round(sum(r["turn_ok"] for r in sel) / len(sel), 3),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="101-110")
    parser.add_argument("--pages", type=int, default=90)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()
    rows: list[dict] = []
    for seed in parse_seeds(args.seeds):
        rows += run_case(seed, args.pages, args.ocr)
        print(f"seed {seed} done", file=sys.stderr)
    result = summarise(rows)
    result["seeds"] = parse_seeds(args.seeds)
    result["pages"] = args.pages
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
