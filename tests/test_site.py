import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _build(tmp_path):
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(tmp_path / "site")
    return tmp_path / "site"


def test_pages_site_has_share_tags_and_the_replay_files(tmp_path):
    site = _build(tmp_path)
    html = (site / "index.html").read_text()
    for tag in ("og:title", "og:description", "og:image", "twitter:card", 'name="description"', 'rel="canonical"'):
        assert tag in html
    assert "__TOKEN__" not in html and html.index("demo.js") < html.index("app.js")
    assert (site / "assets" / "social-card.png").is_file()
    assert (site / "demo" / "no-preview.svg").is_file()


def test_every_candidate_preview_the_replay_lists_exists(tmp_path):
    site = _build(tmp_path)
    state = json.loads((site / "demo" / "state.json").read_text())
    for proposal in state["proposals"]:
        for cand in proposal["candidates"][:6]:
            assert (site / "demo" / f"page-{cand['page'] - 1}.jpg").is_file()


def test_release_workflow_checks_the_tag_against_the_package_version():
    import darnleaf

    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "__version__" in workflow and "GITHUB_REF_NAME" in workflow
    assert f"## Darnleaf {darnleaf.__version__}" in (ROOT / "RELEASE_NOTES.md").read_text()
