"""Run the real matcher on the bundled sample and save the result as static files for the Pages demo.

    python scripts/build_demo.py            # rewrites site-data/demo/

Nothing here is mocked: state.json, the evidence pictures and the receipt all come from the
same Session code that the local app uses. Only the repaired PDF is left out to keep the repo small.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import time
from pathlib import Path

from PIL import Image

from darnleaf.imaging import InputError
from darnleaf.session import Session

OUT = Path(__file__).resolve().parent.parent / "site-data" / "demo"
TOP = 6


def jpeg(png: bytes, quality: int = 70) -> bytes:
    buffer = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    s = Session()
    try:
        s.load_sample()
        s.start()
        while s.stage == "matching":
            time.sleep(0.3)
        if s.stage != "review":
            raise SystemExit(f"match failed: {s.error}")
        state = s.state()
        pages: set[int] = set()
        for p in state["proposals"]:
            cands = p["candidates"][:TOP]
            pages.update(c["page"] - 1 for c in cands)
            turns = {c["quarter_turns"] for c in cands} | {0}
            for t in turns:
                (OUT / f"rescan-{p['rescan']}-t{t}.jpg").write_bytes(jpeg(s.rescan_image(p["rescan"], 900, t)))
            if cands:
                top = cands[0]["page"] - 1
                for kind in ("overlay", "features"):
                    # Not every pair can draw every view; the UI shows a message for the ones that are missing.
                    with contextlib.suppress(InputError):
                        (OUT / f"ev-{p['rescan']}-{top}-{kind}.jpg").write_bytes(jpeg(s.evidence_image(p["rescan"], top, kind), 66))
        for page in sorted(pages):
            (OUT / f"page-{page}.jpg").write_bytes(jpeg(s.page_image(page, 700)))
        for r, p in enumerate(state["proposals"]):
            if p["page"] is not None and p["status"] != "none":
                s.set_choice(r, p["page"] - 1, True)
        receipt = s.export()
        state["receipt"] = {k: v for k, v in receipt.items() if k != "created"}
        (OUT / "state.json").write_text(json.dumps(state, ensure_ascii=False))
    finally:
        s.close()
    size = sum(f.stat().st_size for f in OUT.iterdir())
    print(f"wrote {len(list(OUT.iterdir()))} files, {size / 1e6:.1f} MB, to {OUT}")


if __name__ == "__main__":
    main()
