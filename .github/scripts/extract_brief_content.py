"""One-off helper: copy brief/N/index.html body into content/brief-N.md. Run from repo root."""

from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BRIEFS: dict[int, dict[str, str]] = {
    1: {
        "date": "2026-10-12",
        "date_modified": "2026-10-17",
        "series": "Weekly brief",
        "homepage_blurb": (
            "What the Council decided from Sept. 15 to Oct. 6, and why the "
            "Police Department’s recruiting overtime ran over budget."
        ),
        "coverage_label": "Weekly brief · Oct 12, 2026 (corrected Oct 14) · Brief No. 1",
    },
    2: {
        "date": "2026-10-15",
        "series": "Promised vs. Actual",
        "homepage_blurb": (
            "What the City first planned for three Measure T fire stations and the "
            "police training center, and where each stands today."
        ),
        "coverage_label": "Promised vs. Actual · Oct 15, 2026 · Brief No. 2",
        "meta_line": "By J Gonzales · City records last checked October 14, 2026",
        "og_title": "Brief #2 — The San Jose Source",
    },
}


def meta_content(page: str, name: str) -> str:
    m = re.search(
        rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"',
        page,
        re.I,
    )
    if not m:
        m = re.search(
            rf'<meta\s+content="([^"]*)"\s+name="{re.escape(name)}"',
            page,
            re.I,
        )
    if not m:
        raise ValueError(f"missing meta {name}")
    return html_lib.unescape(m.group(1))


def og_content(page: str, prop: str) -> str:
    m = re.search(
        rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"',
        page,
        re.I,
    )
    if not m:
        raise ValueError(f"missing og {prop}")
    return html_lib.unescape(m.group(1))


def extract_body(page: str) -> str:
    m = re.search(
        r'<p class="brief__meta[^"]*"[^>]*>.*?</p>\s*(.*?)\s*<p class="brief__signoff',
        page,
        re.S,
    )
    if not m:
        raise ValueError("body extract failed")
    return "\n".join(line.rstrip() for line in m.group(1).strip("\n").splitlines())


def extract_eyebrow(page: str) -> str:
    m = re.search(r'<p class="eyebrow[^"]*"[^>]*>(.*?)</p>', page, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def extract_dek(page: str) -> str:
    m = re.search(r'<p class="brief__dek[^"]*"[^>]*>(.*?)</p>', page, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def extract_title_tag(page: str) -> str:
    m = re.search(r"<title>(.*?)</title>", page, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def extract_h1(page: str) -> str:
    m = re.search(r'<h1 class="brief__title[^"]*"[^>]*>(.*?)</h1>', page, re.S)
    if not m:
        raise ValueError("missing h1")
    return re.sub(r"\s+", " ", m.group(1)).strip()


def main() -> int:
    for num, extra in BRIEFS.items():
        src = ROOT / "brief" / str(num) / "index.html"
        page = src.read_text(encoding="utf-8")
        fm: dict[str, str] = {
            "title": extract_h1(page),
            "description": meta_content(page, "description"),
            "date": extra["date"],
            "series": extra["series"],
            "homepage_blurb": extra["homepage_blurb"],
            "coverage_label": extra["coverage_label"],
            "eyebrow": extract_eyebrow(page),
            "body_format": "html",
            "og_title": extra.get("og_title", og_content(page, "og:title")),
            "og_description": og_content(page, "og:description"),
            "page_title": extract_title_tag(page),
        }
        if extra.get("date_modified"):
            fm["date_modified"] = extra["date_modified"]
        dek = extract_dek(page)
        if dek:
            fm["dek"] = dek
        if extra.get("meta_line"):
            fm["meta_line"] = extra["meta_line"]
        lines = ["---", *[f"{k}: {v}" for k, v in fm.items() if v], "---", "", extract_body(page)]
        out = ROOT / "content" / f"brief-{num}.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"Wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
