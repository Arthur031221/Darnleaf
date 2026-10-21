import numpy as np
import pytest
from PIL import Image

from darnleaf import imaging, limits
from darnleaf.imaging import InputError

from .conftest import pdf_with


def test_unsupported_suffix_is_rejected(tmp_path):
    f = tmp_path / "x.docx"
    f.write_bytes(b"x")
    with pytest.raises(InputError):
        imaging.expand_sources([f])


def test_pdf_rescans_expand_to_one_source_per_page(tmp_path):
    sources = imaging.expand_sources([pdf_with(tmp_path / "r.pdf", pages=3)])
    assert [s.page for s in sources] == [0, 1, 2]
    assert sources[1].load().size[0] > 100


def test_replacement_limit(tmp_path):
    with pytest.raises(InputError):
        imaging.expand_sources([pdf_with(tmp_path / "r.pdf", pages=limits.MAX_REPLACEMENTS + 1)])


def test_unreadable_image_is_a_clean_error(tmp_path):
    f = tmp_path / "x.png"
    f.write_bytes(b"not an image")
    with pytest.raises(InputError):
        imaging.expand_sources([f])[0].load()


def test_scanner_bed_is_cut_away():
    page = np.full((900, 640), 235, dtype=np.uint8)
    page[100:130, 100:540] = 20
    bed = np.full((1000, 760), 30, dtype=np.uint8)
    bed[50:950, 60:700] = page
    cropped = imaging.crop_to_page(bed)
    assert cropped.shape[0] < 1000 and np.median(cropped) > 150


def test_a_plain_page_is_left_alone():
    page = np.full((900, 640), 240, dtype=np.uint8)
    assert imaging.crop_to_page(page).shape == page.shape


def test_exif_orientation_is_honoured(tmp_path):
    img = Image.new("RGB", (200, 100), "white")
    exif = Image.Exif()
    exif[0x0112] = 6
    f = tmp_path / "t.jpg"
    img.save(f, exif=exif)
    assert imaging.expand_sources([f])[0].load().size == (100, 200)


def test_heic_photo_loads_when_the_extra_is_installed(tmp_path):
    pytest.importorskip("pillow_heif")
    f = tmp_path / "IMG_0001.HEIC"
    Image.new("RGB", (120, 160), "white").save(f, format="HEIF")
    (source,) = imaging.expand_sources([f])
    assert source.load().size == (120, 160)


def test_heic_without_the_extra_says_how_to_fix_it(tmp_path, monkeypatch):
    monkeypatch.setattr(imaging, "IMAGE_SUFFIXES", imaging.IMAGE_SUFFIXES - imaging.HEIC_SUFFIXES)
    f = tmp_path / "IMG_0001.heic"
    f.write_bytes(b"x")
    with pytest.raises(InputError, match=r"darnleaf\[heic\]"):
        imaging.expand_sources([f])
