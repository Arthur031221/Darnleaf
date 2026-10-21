import json
from pathlib import Path

import pytest

from darnleaf import imaging, pipeline, sample


@pytest.fixture(scope="session")
def case(tmp_path_factory) -> dict:
    """A 40 page generated booklet with six damaged pages and seven shuffled rescans."""
    root = tmp_path_factory.mktemp("case")
    sample.make_case(root, pages=40, seed=7, replacements=6)
    truth = json.loads((root / "truth.json").read_text())
    return {"dir": root, "pdf": root / "original.pdf", "rescans": sorted((root / "rescans").glob("*.jpg")), "truth": truth}


@pytest.fixture(scope="session")
def matched(case):
    sources = imaging.expand_sources(case["rescans"])
    return sources, pipeline.run(case["pdf"], sources)


def pdf_with(path: Path, pages: int = 3, rotate: int = 0) -> Path:
    """A tiny valid PDF with one text page per entry, for preflight and export tests."""
    import pikepdf

    pdf = pikepdf.Pdf.new()
    for i in range(pages):
        page = pdf.add_blank_page(page_size=(300, 400))
        page.obj["/Contents"] = pdf.make_stream(f"BT /F1 24 Tf 40 300 Td (Page {i + 1}) Tj ET".encode())
        page.obj["/Resources"] = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica)))
        if rotate:
            page.obj["/Rotate"] = rotate
    pdf.save(path)
    return path
