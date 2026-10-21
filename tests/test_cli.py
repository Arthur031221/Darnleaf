import json
from pathlib import Path

import pikepdf

from darnleaf.cli import main


def make(tmp_path, capsys):
    assert main(["sample", str(tmp_path), "--pages", "36", "--replacements", "4", "--seed", "3"]) == 0
    capsys.readouterr()
    return str(tmp_path / "original.pdf"), sorted(str(p) for p in (tmp_path / "rescans").glob("*.jpg"))


def test_match_prints_json_and_apply_writes_pdf_and_receipt(tmp_path, capsys):
    original, rescans = make(tmp_path, capsys)
    assert main(["match", original, *rescans, "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == len(rescans) and {r["status"] for r in rows} <= {"clear", "check", "none"}
    out = tmp_path / "fixed.pdf"
    assert main(["apply", original, *rescans, "-o", str(out), "--accept-check"]) == 0
    assert out.with_suffix(".receipt.json").exists()
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 36


def test_apply_without_anything_safe_is_an_error(tmp_path, capsys):
    original, rescans = make(tmp_path, capsys)
    assert main(["apply", original, rescans[-1], "-o", str(tmp_path / "x.pdf")]) == 2
    assert "darnleaf:" in capsys.readouterr().err


def test_assign_flag_forces_a_page(tmp_path, capsys):
    original, rescans = make(tmp_path, capsys)
    decoy = Path(rescans[-1])
    out = tmp_path / "x.pdf"
    assert main(["apply", original, str(decoy), "-o", str(out), "--assign", f"{decoy.name}=5", "--mode", "fit"]) == 0
    receipt = json.loads(out.with_suffix(".receipt.json").read_text())
    assert [e["page"] for e in receipt["replaced"]] == [5]
    assert receipt["replaced"][0]["confirmed_by"] == "cli: --assign"


def test_bad_assign_is_rejected(tmp_path, capsys):
    original, rescans = make(tmp_path, capsys)
    assert main(["apply", original, rescans[0], "-o", str(tmp_path / "x.pdf"), "--assign", "nope=2"]) == 2


def test_serve_refuses_a_non_loopback_host(capsys):
    assert main(["serve", "--host", "0.0.0.0", "--no-open"]) == 2
    assert "refusing to listen" in capsys.readouterr().err


def test_serve_needs_the_original_and_a_rescan_together(tmp_path, capsys):
    original, rescans = make(tmp_path, capsys)
    assert main(["serve", "--port", "0", "--no-open", original]) == 2
    assert "at least one rescan" in capsys.readouterr().err


def test_serve_with_an_unreadable_file_fails_before_it_listens(tmp_path, capsys):
    original, rescans = make(tmp_path, capsys)
    assert main(["serve", "--port", "0", "--no-open", original, str(tmp_path / "nope.jpg")]) == 2
    assert "darnleaf:" in capsys.readouterr().err
