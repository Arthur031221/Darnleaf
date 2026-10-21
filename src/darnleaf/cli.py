"""Command line entry point: serve the UI, print matches, apply them, or write a sample job."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from . import __version__, export, imaging, ocr, pipeline, preflight
from .imaging import InputError


def _progress(stage: str, done: int, total: int) -> None:
    if sys.stderr.isatty():
        print(f"\r{stage}: {done}/{total}   ", end="", file=sys.stderr, flush=True)
        if done == total:
            print(file=sys.stderr)


def _run(args) -> tuple[list, list]:
    report = preflight.check(args.original)
    for line in report.warnings:
        print(f"warning: {line}", file=sys.stderr)
    if not report.ok:
        raise InputError("; ".join(report.errors))
    sources = imaging.expand_sources(args.rescans)
    return sources, pipeline.run(args.original, sources, _progress, use_ocr=args.ocr and ocr.available() is not None)


def cmd_match(args) -> int:
    sources, proposals = _run(args)
    if args.json:
        print(json.dumps([{"file": sources[p.rescan].label, **p.public()} for p in proposals], indent=2))
        return 0
    print(f"{'rescan':<28} {'page':>5}  {'status':<6}  reason")
    for p in proposals:
        page = "-" if p.page is None else str(p.page + 1)
        print(f"{sources[p.rescan].label[:28]:<28} {page:>5}  {p.status:<6}  {p.reason}")
    return 0


def cmd_apply(args) -> int:
    sources, proposals = _run(args)
    by_name = {s.label: i for i, s in enumerate(sources)}
    forced: dict[int, int] = {}
    for item in args.assign or []:
        name, _, page = item.rpartition("=")
        if name not in by_name or not page.isdigit():
            raise InputError(f"--assign wants FILE=PAGE with a file you passed in, got {item!r}")
        forced[by_name[name]] = int(page) - 1
    items = []
    for p in proposals:
        chosen, how = None, ""
        if p.rescan in forced:
            chosen, how = forced[p.rescan], "cli: --assign"
        elif p.status == "clear" and p.page is not None:
            chosen, how = p.page, "matcher: clear"
        elif p.status == "check" and p.page is not None and args.accept_check:
            chosen, how = p.page, "cli: --accept-check"
        if chosen is None:
            print(f"skipped {sources[p.rescan].label}: {p.status}, {p.reason}", file=sys.stderr)
            continue
        cand = next((c for c in p.candidates if c.page == chosen), None)
        items.append(export.Replacement(chosen, sources[p.rescan], cand.quarter_turns if cand else 0, cand.public() if cand else {"note": "assigned by hand"}, how))
    if not items:
        raise InputError("no page was safe to replace; use --assign FILE=PAGE or --accept-check")
    receipt_path = args.output.with_suffix(".receipt.json")
    receipt = export.export(args.original, items, args.output, receipt_path, mode=args.mode, quality=args.quality, drop_annotations=args.drop_annotations)
    print(f"replaced {len(receipt['replaced'])} of {receipt['original']['pages']} pages -> {args.output}")
    print(f"receipt -> {receipt_path}")
    return 0


def cmd_sample(args) -> int:
    from . import sample

    truth = sample.make_case(args.directory, pages=args.pages, seed=args.seed, replacements=args.replacements)
    print(f"wrote {args.directory}/original.pdf, {len(truth)} rescans and truth.json")
    return 0


def cmd_serve(args) -> int:
    from .server import App

    app = App(args.host, args.port)
    print(f"Darnleaf {__version__} is running at {app.url}  (Ctrl+C to stop)", flush=True)
    if not args.no_open:
        webbrowser.open(app.url)
    try:
        app.serve()
    except KeyboardInterrupt:
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="darnleaf", description="Repair a scanned PDF with fresh rescans, locally.")
    parser.add_argument("--version", action="version", version=f"darnleaf {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="open the review UI in your browser")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(run=cmd_serve)

    for name, helptext, run in (("match", "print the suggested page for each rescan", cmd_match), ("apply", "write a repaired PDF and a receipt", cmd_apply)):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("original", type=Path)
        p.add_argument("rescans", type=Path, nargs="+")
        p.add_argument("--ocr", action="store_true", help="use text as a second signal when an OCR engine is installed")
        if name == "match":
            p.add_argument("--json", action="store_true")
        else:
            p.add_argument("-o", "--output", type=Path, required=True)
            p.add_argument("--assign", action="append", metavar="FILE=PAGE", help="force a rescan onto a 1-based page")
            p.add_argument("--accept-check", action="store_true", help="also use matches labelled check")
            p.add_argument("--mode", choices=["align", "fit"], default="align")
            p.add_argument("--quality", type=int, default=92)
            p.add_argument("--drop-annotations", action="store_true")
        p.set_defaults(run=run)

    p = sub.add_parser("sample", help="write a synthetic damaged booklet with shuffled rescans")
    p.add_argument("directory", type=Path)
    p.add_argument("--pages", type=int, default=40)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--replacements", type=int, default=6)
    p.set_defaults(run=cmd_sample)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except InputError as exc:
        print(f"darnleaf: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
