import pikepdf

from darnleaf import limits, preflight

from .conftest import pdf_with


def test_plain_pdf_passes(tmp_path):
    report = preflight.check(pdf_with(tmp_path / "a.pdf"))
    assert report.ok and report.pages == 3 and not report.warnings


def test_encrypted_pdf_is_refused(tmp_path):
    src = pdf_with(tmp_path / "a.pdf")
    with pikepdf.open(src) as pdf:
        pdf.save(tmp_path / "enc.pdf", encryption=pikepdf.Encryption(owner="x", user="y"))
    report = preflight.check(tmp_path / "enc.pdf")
    assert not report.ok and any("encrypt" in e or "password" in e for e in report.errors)


def test_signed_pdf_is_refused(tmp_path):
    src = pdf_with(tmp_path / "a.pdf")
    with pikepdf.open(src) as pdf:
        pdf.Root.AcroForm = pikepdf.Dictionary(SigFlags=3, Fields=pikepdf.Array())
        pdf.save(tmp_path / "signed.pdf")
    assert any("signature" in e for e in preflight.check(tmp_path / "signed.pdf").errors)


def test_odd_rotation_is_refused(tmp_path):
    path = pdf_with(tmp_path / "a.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj["/Rotate"] = 45
        pdf.save(path)
    assert not preflight.check(path).ok


def test_annotations_are_reported_per_page(tmp_path):
    path = pdf_with(tmp_path / "a.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[1].obj["/Annots"] = pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[0, 0, 10, 10]))])
        pdf.save(path)
    report = preflight.check(path)
    assert report.ok and report.annotated_pages == [1]


def test_page_limit(tmp_path):
    report = preflight.check(pdf_with(tmp_path / "big.pdf", pages=limits.MAX_ORIGINAL_PAGES + 1))
    assert not report.ok


def test_garbage_is_refused(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"not a pdf at all")
    assert not preflight.check(path).ok


def test_form_fields_are_refused(tmp_path):
    src = pdf_with(tmp_path / "a.pdf")
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        field = pdf.make_indirect(pikepdf.Dictionary(FT=pikepdf.Name.Tx, T=pikepdf.String("name"), Subtype=pikepdf.Name.Widget))
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([field]))
        pdf.save()
    report = preflight.check(src)
    assert not report.ok and any("form" in e for e in report.errors)


def test_malformed_objects_become_errors_not_crashes(tmp_path):
    for name, damage in {
        "rotate": lambda pdf: pdf.pages[0].obj.__setitem__("/Rotate", pikepdf.String("x")),
        "sigflags": lambda pdf: setattr(pdf.Root, "AcroForm", pikepdf.Dictionary(SigFlags=pikepdf.String("x"))),
        "emptybox": lambda pdf: pdf.pages[1].obj.__setitem__("/MediaBox", pikepdf.Array([0, 0, 0, 0])),
    }.items():
        src = pdf_with(tmp_path / f"{name}.pdf")
        with pikepdf.open(src, allow_overwriting_input=True) as pdf:
            damage(pdf)
            pdf.save()
        report = preflight.check(src)
        assert not report.ok and report.errors, name
