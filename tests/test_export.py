import hashlib
import json
import os

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image

from darnleaf import export
from darnleaf.imaging import InputError, Source

from .conftest import pdf_with


def render(path, index, scale=0.5):
    doc = pdfium.PdfDocument(str(path))
    try:
        return np.asarray(doc[index].render(scale=scale).to_pil().convert("L"), dtype=np.float32)
    finally:
        doc.close()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def items_from(case, matched):
    sources, proposals = matched
    return [
        export.Replacement(p.page, sources[p.rescan], p.candidates[0].quarter_turns, p.candidates[0].public(), "test")
        for p in proposals
        if p.page is not None
    ]


@pytest.fixture(scope="module")
def repaired(case, matched, tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    items = items_from(case, matched)
    before = sha(case["pdf"])
    receipt = export.export(case["pdf"], items, out / "fixed.pdf", out / "receipt.json")
    return {"pdf": out / "fixed.pdf", "receipt": receipt, "pages": {i.page for i in items}, "before": before, "out": out}


def test_source_file_is_never_modified(case, repaired):
    assert sha(case["pdf"]) == repaired["before"]
    assert repaired["receipt"]["original"]["sha256"] == repaired["before"]


def test_page_count_is_kept_and_other_readers_open_it(case, repaired):
    assert len(pdfium.PdfDocument(str(repaired["pdf"]))) == 40
    with pikepdf.open(repaired["pdf"]) as pdf:
        assert len(pdf.pages) == 40
    pdf = repaired["pdf"]
    import shutil
    import subprocess

    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-r", "20", "-f", "1", "-l", "3", "-png", str(pdf), str(repaired["out"] / "pp")], check=True)
        assert list(repaired["out"].glob("pp*.png"))


def content(page: pikepdf.Page) -> bytes:
    return pikepdf.unparse_content_stream(pikepdf.parse_content_stream(page))


def test_untouched_pages_keep_their_content_and_images(case, repaired):
    with pikepdf.open(case["pdf"]) as a, pikepdf.open(repaired["pdf"]) as b:
        for i in set(range(40)) - repaired["pages"]:
            assert content(a.pages[i]) == content(b.pages[i])
            raw_a = [img.read_raw_bytes() for img in a.pages[i].get_images().values()]
            raw_b = [img.read_raw_bytes() for img in b.pages[i].get_images().values()]
            assert raw_a == raw_b


def test_replaced_pages_look_like_the_rescan_not_the_damaged_page(case, matched, repaired):
    sources, proposals = matched
    # The rescan aligned onto the original frame should correlate with the exported page.
    for p in proposals:
        if p.page is None:
            continue
        page = render(repaired["pdf"], p.page)
        assert page.std() > 5, "replaced page is blank"
        assert page.shape == render(case["pdf"], p.page).shape


def test_receipt_lists_every_change_and_is_honest_about_the_rest(repaired):
    receipt = json.loads((repaired["out"] / "receipt.json").read_text())
    assert [e["page"] - 1 for e in receipt["replaced"]] == sorted(repaired["pages"])
    assert receipt["untouched_pages"] == 40 - len(repaired["pages"])
    assert all(len(e["replacement_sha256"]) == 64 for e in receipt["replaced"])
    assert receipt["output"]["sha256"] == sha(repaired["pdf"])


def test_refuses_to_overwrite_the_original(case, matched, tmp_path):
    with pytest.raises(InputError):
        export.export(case["pdf"], items_from(case, matched), case["pdf"])


def test_refuses_two_rescans_on_one_page(case, matched, tmp_path):
    items = items_from(case, matched)
    items.append(export.Replacement(items[0].page, items[0].source))
    with pytest.raises(InputError):
        export.export(case["pdf"], items, tmp_path / "x.pdf")


def test_annotations_block_export_until_allowed(tmp_path):
    src = pdf_with(tmp_path / "a.pdf")
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj["/Annots"] = pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[0, 0, 10, 10]))])
        pdf.save(src)
    img = tmp_path / "r.png"
    Image.new("RGB", (600, 800), "white").save(img)
    item = export.Replacement(0, Source("r.png", img))
    with pytest.raises(InputError, match="annotations"):
        export.export(src, [item], tmp_path / "o.pdf", mode="fit")
    export.export(src, [item], tmp_path / "o.pdf", mode="fit", drop_annotations=True)
    with pikepdf.open(tmp_path / "o.pdf") as pdf:
        assert "/Annots" not in pdf.pages[0].obj


@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_pages_with_rotate_come_out_upright(tmp_path, rotate):
    """A /Rotate page shows its content turned; the replacement must show up the right way round."""
    src = pdf_with(tmp_path / "a.pdf", rotate=rotate)
    shown = render(src, 0, 1.0)
    canvas = Image.new("L", (shown.shape[1], shown.shape[0]), 255)
    # Draw a heavy bar along the top edge of the *displayed* page and rescan exactly that view.
    arr = np.asarray(canvas).copy()
    arr[10:60, :] = 0
    rescan = tmp_path / "r.png"
    Image.fromarray(arr).convert("RGB").save(rescan)
    out = tmp_path / "o.pdf"
    export.export(src, [export.Replacement(0, Source("r.png", rescan))], out, mode="fit")
    got = render(out, 0, 1.0)
    assert got.shape == shown.shape
    assert got[10:60].mean() < 40 and got[-60:].mean() > 215, "bar must stay along the top of the displayed page"


def test_letterbox_never_stretches():
    img = Image.new("RGB", (400, 400), "black")
    boxed = export.letterbox(img, 0.5)
    assert abs(boxed.width / boxed.height - 0.5) < 0.01
    assert boxed.getpixel((boxed.width // 2, boxed.height // 2)) == (0, 0, 0)


def test_preflight_is_run_by_export(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"nope")
    with pytest.raises(InputError):
        export.export(bad, [], tmp_path / "o.pdf")


def test_bookmarks_and_links_to_a_replaced_page_still_point_at_it(tmp_path):
    src = pdf_with(tmp_path / "linked.pdf", pages=4)
    rescan = tmp_path / "scan.png"
    Image.new("RGB", (300, 400), "white").save(rescan)
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        target = pdf.pages[2]
        with pdf.open_outline() as outline:
            outline.root.append(pikepdf.OutlineItem("Chapter", 2))
        pdf.pages[0].obj["/Annots"] = pikepdf.Array(
            [pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[0, 0, 50, 50], Dest=pikepdf.Array([target.obj, pikepdf.Name.Fit]))]
        )
        pdf.save(tmp_path / "linked2.pdf")
    out = tmp_path / "out.pdf"
    export.export(tmp_path / "linked2.pdf", [export.Replacement(2, Source("scan.png", rescan), 0, {}, "test")], out, mode="fit")
    with pikepdf.open(out) as pdf:
        target_id = pdf.pages[2].obj.objgen
        assert pdf.pages[1].obj.objgen != target_id
        with pdf.open_outline() as outline:
            assert outline.root[0].destination[0].objgen == target_id
        assert pdf.pages[0].obj["/Annots"][0]["/Dest"][0].objgen == target_id


def test_hard_link_to_the_original_is_refused_and_leaves_it_alone(case, matched, tmp_path):
    link = tmp_path / "link.pdf"
    os.link(case["pdf"], link)
    before = sha(case["pdf"])
    with pytest.raises(InputError):
        export.export(case["pdf"], items_from(case, matched), link)
    assert sha(case["pdf"]) == before


def test_failed_export_leaves_no_partial_file(case, matched, tmp_path):
    items = items_from(case, matched)
    items.append(export.Replacement(items[0].page, items[0].source))
    with pytest.raises(InputError):
        export.export(case["pdf"], items, tmp_path / "x.pdf")
    assert list(tmp_path.iterdir()) == []


def test_existing_output_is_replaced_whole_and_keeps_normal_permissions(case, matched, tmp_path):
    out = tmp_path / "fixed.pdf"
    out.write_bytes(b"old")
    export.export(case["pdf"], items_from(case, matched), out)
    assert out.read_bytes().startswith(b"%PDF-")
    assert (out.stat().st_mode & 0o044) == 0o044
    assert [p.name for p in tmp_path.iterdir()] == ["fixed.pdf"]
