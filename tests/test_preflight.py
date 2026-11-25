import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("preflight", Path(__file__).resolve().parents[1] / "tools" / "preflight.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)


def test_right_repo_forms():
    assert pf.repo_ok("https://github.com/knightingale408/thesanjosesource")
    assert pf.repo_ok("https://github.com/knightingale408/thesanjosesource.git")
    assert pf.repo_ok("git@github.com:knightingale408/thesanjosesource.git")
    assert pf.repo_ok("knightingale408/thesanjosesource")


def test_wrong_repos_rejected():
    assert not pf.repo_ok("https://github.com/knightingale408/fiscal-os")
    assert not pf.repo_ok("https://github.com/knightingale408/san-jose-sourcearchive")
    assert not pf.repo_ok("https://github.com/knightingale408/san-jose-source.git")
    assert not pf.repo_ok("")
    assert not pf.repo_ok(None)


def test_queued_brief_overlap():
    queued = {"content/brief-6.md": "open PR #80"}
    assert pf.queued_overlap(["content/brief-6.md", "styles.css"], queued) == [("content/brief-6.md", "open PR #80")]
    assert pf.queued_overlap(["content/brief-5.md", "content/README.md"], queued) == []
    assert pf.brief_files(["content/README.md", "brief/6/index.html", "content/brief-12.md"]) == ["content/brief-12.md"]
