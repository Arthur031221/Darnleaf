"""One repair job held in a private temp directory: uploads, a match run, choices and export."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import threading
from pathlib import Path

from PIL import Image

from . import evidence, export, imaging, limits, ocr, pipeline, preflight
from .imaging import InputError, Source
from .matcher import Cancelled, Proposal


def _safe_name(name: str, fallback: str) -> str:
    stem = "".join(c for c in Path(name).name if c.isalnum() or c in "._- ")[:80].strip(". ")
    return stem or fallback


class Session:
    def __init__(self, root: Path | None = None):
        self.dir = Path(tempfile.mkdtemp(prefix="darnleaf-", dir=root))
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.original: Path | None = None
        self.original_name = ""
        self.report: preflight.Report | None = None
        self.sources: list[Source] = []
        self.proposals: list[Proposal] = []
        self.choice: dict[int, int | None] = {}
        self.confirmed: set[int] = set()
        self.stage, self.stage_name, self.done, self.total = "idle", "", 0, 0
        self.error = ""
        self.thread: threading.Thread | None = None
        self.output: Path | None = None
        self.receipt: dict | None = None
        self.use_ocr = False

    def close(self) -> None:
        self.cancel.set()
        shutil.rmtree(self.dir, ignore_errors=True)

    # ----- uploads -------------------------------------------------------------

    def _check_idle(self) -> None:
        if self.stage in ("matching",):
            raise InputError("wait for the match to finish or cancel it first")

    def _reset_results(self) -> None:
        self.proposals, self.choice, self.confirmed = [], {}, set()
        self.output, self.receipt = None, None
        self.stage = "ready" if self.original and self.sources else "idle"

    def set_original(self, name: str, data: bytes) -> dict:
        with self.lock:
            self._check_idle()
            if len(data) > limits.MAX_ORIGINAL_BYTES:
                raise InputError("the original is over the size limit")
            path = self.dir / "original.pdf"
            path.write_bytes(data)
            report = preflight.check(path)
            if not report.ok:
                path.unlink(missing_ok=True)
                raise InputError("; ".join(report.errors))
            self.original, self.report, self.original_name = path, report, _safe_name(name, "original.pdf")
            self._reset_results()
            return report.public()

    def add_rescan(self, name: str, data: bytes) -> int:
        with self.lock:
            self._check_idle()
            if len(data) > limits.MAX_REPLACEMENT_BYTES:
                raise InputError(f"{name}: over the size limit")
            folder = self.dir / "rescans"
            folder.mkdir(exist_ok=True)
            safe = _safe_name(name, "rescan")
            path = folder / f"{len(list(folder.iterdir())) + 1:03d}-{safe}"
            path.write_bytes(data)
            try:
                found = imaging.expand_sources([path])
                if len(self.sources) + len(found) > limits.MAX_REPLACEMENTS:
                    raise InputError(f"more than {limits.MAX_REPLACEMENTS} replacement pages")
                for s in found:
                    s.label = s.label.split("-", 1)[1] if s.label[:3].isdigit() else s.label
                    s.load()
            except InputError:
                path.unlink(missing_ok=True)
                raise
            self.sources.extend(found)
            self._reset_results()
            return len(found)

    def clear_rescans(self) -> None:
        with self.lock:
            self._check_idle()
            self.sources = []
            shutil.rmtree(self.dir / "rescans", ignore_errors=True)
            self._reset_results()

    def load_sample(self) -> None:
        from . import sample

        with self.lock:
            self._check_idle()
            self.sources = []
            shutil.rmtree(self.dir / "rescans", ignore_errors=True)
            case = self.dir / "sample"
            sample.make_case(case, pages=40, seed=7, replacements=6)
            self.set_original("sample-booklet.pdf", (case / "original.pdf").read_bytes())
            for f in sorted((case / "rescans").iterdir()):
                self.add_rescan(f.name, f.read_bytes())

    # ----- matching ------------------------------------------------------------

    def start(self, use_ocr: bool = False) -> None:
        with self.lock:
            self._check_idle()
            if self.original is None or not self.sources:
                raise InputError("add the original PDF and at least one replacement first")
            self.cancel.clear()
            self.stage, self.done, self.total, self.error = "matching", 0, 1, ""
            self.use_ocr = use_ocr and ocr.available() is not None
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _progress(self, stage: str, done: int, total: int) -> None:
        self.stage_name, self.done, self.total = stage, done, total

    def _run(self) -> None:
        try:
            proposals = pipeline.run(self.original, list(self.sources), self._progress, self.cancel, self.use_ocr)
        except Cancelled:
            with self.lock:
                self.stage = "ready"
            return
        except Exception as exc:  # shown to the user; the thread must not die silently
            with self.lock:
                self.stage, self.error = "failed", f"{type(exc).__name__}: {exc}"
            return
        with self.lock:
            self.proposals = proposals
            self.choice = {p.rescan: p.page for p in proposals if p.page is not None and p.status != "none"}
            self.confirmed = set()
            self.stage = "review"

    def cancel_match(self) -> None:
        self.cancel.set()

    # ----- review --------------------------------------------------------------

    def set_choice(self, rescan: int, page: int | None, confirmed: bool) -> None:
        with self.lock:
            if not 0 <= rescan < len(self.sources):
                raise InputError("no such rescan")
            if page is not None and not 0 <= page < (self.report.pages if self.report else 0):
                raise InputError("no such page")
            if page is None:
                self.choice.pop(rescan, None)
                self.confirmed.discard(rescan)
            else:
                self.choice[rescan] = page
                (self.confirmed.add if confirmed else self.confirmed.discard)(rescan)

    def state(self) -> dict:
        with self.lock:
            taken: dict[int, list[int]] = {}
            for r, p in self.choice.items():
                taken.setdefault(p, []).append(r)
            return {
                "stage": self.stage,
                "step": self.stage_name,
                "done": self.done,
                "total": self.total,
                "error": self.error,
                "original": None if self.report is None else {"name": self.original_name, **self.report.public()},
                "rescans": [{"index": i, "label": s.label} for i, s in enumerate(self.sources)],
                "proposals": [p.public() for p in self.proposals],
                "choice": {str(r): None if p is None else p + 1 for r, p in self.choice.items()},
                "confirmed": sorted(self.confirmed),
                "conflicts": sorted(p + 1 for p, rs in taken.items() if len(rs) > 1),
                "ocr": ocr.available(),
                "limits": {"pages": limits.MAX_ORIGINAL_PAGES, "replacements": limits.MAX_REPLACEMENTS},
                "exported": self.output is not None,
            }

    # ----- images --------------------------------------------------------------

    def _png(self, img: Image.Image, longest: int) -> bytes:
        img = img.convert("RGB")
        img.thumbnail((longest, longest))
        buffer = io.BytesIO()
        img.save(buffer, "PNG", optimize=False, compress_level=3)
        return buffer.getvalue()

    def page_image(self, index: int, longest: int = 700) -> bytes:
        if self.original is None or not 0 <= index < (self.report.pages if self.report else 0):
            raise InputError("no such page")
        return self._png(imaging.render_pdf_page(self.original, index, longest=longest), longest)

    def rescan_image(self, index: int, longest: int = 700, turns: int = 0) -> bytes:
        if not 0 <= index < len(self.sources):
            raise InputError("no such rescan")
        img = self.sources[index].load()
        if turns:
            img = img.rotate(-90 * (turns % 4), expand=True)
        return self._png(img, longest)

    def _upright(self, rescan: int, page: int) -> tuple[Image.Image, Image.Image]:
        turns = self._turns(rescan, page)
        img = self.sources[rescan].load()
        if turns:
            img = img.rotate(-90 * turns, expand=True)
        return img, imaging.render_pdf_page(self.original, page, longest=1000)

    def _turns(self, rescan: int, page: int) -> int:
        if rescan < len(self.proposals):
            for c in self.proposals[rescan].candidates:
                if c.page == page:
                    return c.quarter_turns
        return 0

    def evidence_image(self, rescan: int, page: int, kind: str) -> bytes:
        if not (0 <= rescan < len(self.sources) and self.original and 0 <= page < self.report.pages):
            raise InputError("no such pair")
        img, target = self._upright(rescan, page)
        if kind == "features":
            out = evidence.match_map(img, target)
            if out is None:
                raise InputError("Too few shared features to draw.")
            return self._png(out, 1600)
        aligned = evidence.align(img, target)
        if aligned is None:
            raise InputError("these two do not line up well enough to compare")
        if kind == "aligned":
            return self._png(aligned, 1000)
        if kind == "overlay":
            return self._png(evidence.difference(aligned, target), 1000)
        raise InputError("unknown evidence view")

    # ----- export --------------------------------------------------------------

    def export(self, mode: str = "align", drop_annotations: bool = False) -> dict:
        with self.lock:
            if self.original is None or not self.choice:
                raise InputError("nothing is assigned yet")
            items = []
            unsure = [
                r + 1
                for r, p in self.choice.items()
                if r not in self.confirmed and not (r < len(self.proposals) and self.proposals[r].status == "clear" and self.proposals[r].page == p)
            ]
            if unsure:
                raise InputError(f"confirm rescans {unsure} before exporting: the matcher was not sure about them")
            for rescan, page in sorted(self.choice.items(), key=lambda kv: kv[1]):
                cands = self.proposals[rescan].candidates if rescan < len(self.proposals) else []
                match = next((c for c in cands if c.page == page), None)
                items.append(
                    export.Replacement(
                        page,
                        self.sources[rescan],
                        match.quarter_turns if match else 0,
                        match.public() if match else {"note": "assigned by hand"},
                        "user" if rescan in self.confirmed else "matcher: clear",
                    )
                )
            stem = Path(self.original_name).stem
            out_pdf, receipt = self.dir / f"{stem}-repaired.pdf", self.dir / f"{stem}-receipt.json"
            self.receipt = export.export(self.original, items, out_pdf, receipt, mode=mode, drop_annotations=drop_annotations, label=self.original_name)
            self.output = out_pdf
            return self.receipt

    def download(self, which: str) -> tuple[str, bytes, str]:
        if self.output is None:
            raise InputError("export first")
        if which == "pdf":
            return self.output.name, self.output.read_bytes(), "application/pdf"
        return self.output.with_name(self.output.stem.removesuffix("-repaired") + "-receipt.json").name, json.dumps(self.receipt, indent=2).encode(), "application/json"
