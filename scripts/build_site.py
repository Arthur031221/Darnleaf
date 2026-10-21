"""Assemble the GitHub Pages site: the real web UI plus the replay backend and its data.

    python scripts/build_site.py _site
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://arthur031221.github.io/Darnleaf/"
TITLE = "Darnleaf: swap damaged scanned PDF pages for fresh rescans"
BLURB = "Match rescans to the pages they replace, review the evidence and export a repaired PDF with a receipt. Runs on your own computer."
SOCIAL = f"""<meta name="description" content="{BLURB}">
<link rel="canonical" href="{SITE}">
<meta property="og:type" content="website">
<meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{BLURB}">
<meta property="og:url" content="{SITE}">
<meta property="og:image" content="{SITE}assets/social-card.png">
<meta name="twitter:card" content="summary_large_image">
"""


def main(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(ROOT / "src" / "darnleaf" / "web", out)
    shutil.copy(ROOT / "site-data" / "demo.js", out / "demo.js")
    shutil.copytree(ROOT / "site-data" / "demo", out / "demo")
    shutil.copy(ROOT / "site-data" / "no-preview.svg", out / "demo" / "no-preview.svg")
    shutil.copytree(ROOT / "assets", out / "assets", ignore=shutil.ignore_patterns("*.html"))
    html = (out / "index.html").read_text()
    html = html.replace("</head>", SOCIAL + "</head>", 1)
    html = html.replace('<script src="app.js">', '<script src="demo.js"></script>\n<script src="app.js">').replace("__TOKEN__", "static-demo")
    (out / "index.html").write_text(html)
    (out / ".nojekyll").write_text("")
    print(f"site written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "_site"))
