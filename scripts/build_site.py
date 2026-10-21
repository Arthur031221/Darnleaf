"""Assemble the GitHub Pages site: the real web UI plus the replay backend and its data.

    python scripts/build_site.py _site
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(ROOT / "src" / "darnleaf" / "web", out)
    shutil.copy(ROOT / "site-data" / "demo.js", out / "demo.js")
    shutil.copytree(ROOT / "site-data" / "demo", out / "demo")
    shutil.copytree(ROOT / "assets", out / "assets", ignore=shutil.ignore_patterns("*.html"))
    html = (out / "index.html").read_text()
    html = html.replace('<script src="app.js">', '<script src="demo.js"></script>\n<script src="app.js">').replace("__TOKEN__", "static-demo")
    (out / "index.html").write_text(html)
    (out / ".nojekyll").write_text("")
    print(f"site written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "_site"))
