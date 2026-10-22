#!/usr/bin/env python3
"""
Compile markdown briefs in content/ into static HTML pages and refresh site indexes.

Usage:
  python build.py

Each source file must be named brief-N.md (e.g. content/brief-1.md). Front matter
at the top of the file (YAML-like, between --- lines) supplies metadata; the body
is markdown converted to HTML inside the standard brief page shell.

Required front matter keys: title, description, date (YYYY-MM-DD)
Optional: dek, eyebrow, series, homepage_blurb, coverage_label, date_modified,
          og_title, og_type (defaults to website), author (defaults to J Gonzales),
          meta_line (replaces default byline), body_format (markdown or html)
"""

from __future__ import annotations

import html
import json
import re
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
SITE_BASE = "https://thesanjosesource.com"
BRIEF_FILENAME = re.compile(r"^brief-(\d+)\.md$", re.IGNORECASE)

MARKER_COVERAGE_START = "<!-- build:coverage-start -->"
MARKER_COVERAGE_END = "<!-- build:coverage-end -->"
MARKER_HERO_START = "<!-- build:hero-latest-start -->"
MARKER_HERO_END = "<!-- build:hero-latest-end -->"


@dataclass
class Brief:
    number: int
    path: Path
    title: str
    description: str
    date: datetime
    body_md: str
    dek: str = ""
    eyebrow: str = ""
    series: str = "Weekly brief"
    homepage_blurb: str = ""
    coverage_label: str = ""
    date_modified: datetime | None = None
    og_title: str = ""
    og_description: str = ""
    page_title: str = ""
    og_type: str = "website"
    author: str = "J Gonzales"
    meta_line: str = ""
    body_format: str = "markdown"

    @property
    def canonical_url(self) -> str:
        return f"{SITE_BASE}/brief/{self.number}/"

    @property
    def sort_date(self) -> datetime:
        """Publication order for homepage and RSS (not correction dates)."""
        return self.date

    def formatted_date_long(self) -> str:
        return self.date.strftime("%B %d, %Y").replace(" 0", " ")

    def formatted_date_short(self) -> str:
        return self.date.strftime("%b %d, %Y").replace(" 0", " ")

    def default_eyebrow(self) -> str:
        if self.eyebrow:
            return self.eyebrow
        return f"{self.series} · Brief No. {self.number} · Published {self.formatted_date_long()}"

    def default_homepage_blurb(self) -> str:
        if self.homepage_blurb:
            return self.homepage_blurb
        return self.description

    def default_coverage_label(self) -> str:
        if self.coverage_label:
            return self.coverage_label
        return f"{self.series} · {self.formatted_date_short()} · Brief No. {self.number}"


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        raise ValueError("Markdown must begin with --- front matter ---")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Unclosed front matter (missing closing ---)")
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    return meta, parts[2].lstrip("\n")


def parse_date(value: str, field: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid {field} date {value!r} (use YYYY-MM-DD)")


def load_brief(path: Path) -> Brief:
    match = BRIEF_FILENAME.match(path.name)
    if not match:
        raise ValueError(f"Unexpected brief filename: {path.name}")
    number = int(match.group(1))
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    title = meta.get("title", "").strip()
    description = meta.get("description", "").strip()
    date_raw = meta.get("date", "").strip()
    if not title or not description or not date_raw:
        raise ValueError(f"{path.name}: front matter requires title, description, and date")
    date_modified = None
    if meta.get("date_modified", "").strip():
        date_modified = parse_date(meta["date_modified"].strip(), "date_modified")
    return Brief(
        number=number,
        path=path,
        title=title,
        description=description,
        date=parse_date(date_raw, "date"),
        body_md=body,
        dek=meta.get("dek", "").strip(),
        eyebrow=meta.get("eyebrow", "").strip(),
        series=meta.get("series", "Weekly brief").strip() or "Weekly brief",
        homepage_blurb=meta.get("homepage_blurb", "").strip(),
        coverage_label=meta.get("coverage_label", "").strip(),
        date_modified=date_modified,
        og_title=meta.get("og_title", "").strip(),
        og_description=meta.get("og_description", "").strip(),
        page_title=meta.get("page_title", "").strip(),
        og_type=meta.get("og_type", "website").strip() or "website",
        author=meta.get("author", "J Gonzales").strip() or "J Gonzales",
        meta_line=meta.get("meta_line", "").strip(),
        body_format=meta.get("body_format", "markdown").strip().lower() or "markdown",
    )


def discover_briefs() -> list[Brief]:
    if not CONTENT_DIR.is_dir():
        return []
    briefs: list[Brief] = []
    for path in sorted(CONTENT_DIR.glob("brief-*.md")):
        briefs.append(load_brief(path))
    return sorted(briefs, key=lambda b: b.number)


def slugify_heading(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def external_link_attrs(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        if "thesanjosesource.com" not in parsed.netloc:
            return ' target="_blank" rel="noopener noreferrer"'
    return ""


def inline_markdown(text: str) -> str:
    """Bold, italic, and links within a line."""
    placeholders: list[str] = []

    def stash(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"\x00{len(placeholders) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: html.escape(m.group(1)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", stash, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = html.escape(text, quote=False)
    text = text.replace("&lt;strong&gt;", "<strong>").replace("&lt;/strong&gt;", "</strong>")
    text = text.replace("&lt;em&gt;", "<em>").replace("&lt;/em&gt;", "</em>")

    def restore(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        link = placeholders[idx]
        m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", link)
        if not m:
            return link
        label, url = m.group(1), m.group(2)
        attrs = external_link_attrs(url)
        return f'<a href="{html.escape(url, quote=True)}"{attrs}>{html.escape(label)}</a>'

    text = re.sub(r"\x00(\d+)\x00", restore, text)
    return text


def is_table_row(line: str) -> bool:
    return "|" in line and line.strip().startswith("|")


def parse_table(lines: list[str]) -> tuple[str, int]:
    rows: list[list[str]] = []
    i = 0
    while i < len(lines) and is_table_row(lines[i]):
        row = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
        rows.append(row)
        i += 1
    if len(rows) < 2:
        return "", 0
    header = rows[0]
    body_rows = rows[1:]
    if body_rows and all(
        re.fullmatch(r":?-+:?", cell.strip()) or not cell.strip() for cell in body_rows[0]
    ):
        body_rows = body_rows[1:]
    out = ['<div class="brief-table-wrap">', '<table class="brief-table">', "<thead><tr>"]
    for cell in header:
        out.append(f"<th scope=\"col\">{inline_markdown(cell)}</th>")
    out.append("</tr></thead><tbody>")
    for row in body_rows:
        out.append("<tr>")
        for cell in row:
            out.append(f"<td>{inline_markdown(cell)}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out), i


def markdown_body_to_html(md: str) -> str:
    lines = md.splitlines()
    i = 0
    chunks: list[str] = []
    current_section: list[str] | None = None
    section_title: str | None = None
    section_id: str | None = None
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            current_section.append("</ul>")
            in_list = False

    def flush_section() -> None:
        nonlocal current_section, section_title, section_id
        if current_section is None:
            return
        close_list()
        inner = "\n".join(current_section).strip()
        if not inner and not section_title:
            current_section = None
            return
        aria = ""
        if section_id:
            aria = f' aria-labelledby="{section_id}"'
        title_html = ""
        if section_title:
            title_html = (
                f'<h2 id="{section_id}" class="brief-block__title">'
                f"{html.escape(section_title)}</h2>\n"
            )
        chunks.append(
            f'<section class="brief-block reveal" data-reveal{aria}>\n{title_html}{inner}\n</section>'
        )
        current_section = None
        section_title = None
        section_id = None

    def ensure_section() -> None:
        nonlocal current_section
        if current_section is None:
            current_section = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            close_list()
            i += 1
            continue

        if stripped.startswith("<"):
            ensure_section()
            close_list()
            current_section.append(line)
            i += 1
            continue

        if stripped.startswith("## "):
            flush_section()
            section_title = stripped[3:].strip()
            section_id = f"{slugify_heading(section_title)}-title"
            current_section = []
            i += 1
            continue

        if stripped.startswith("### "):
            ensure_section()
            close_list()
            sub = stripped[4:].strip()
            sid = slugify_heading(sub)
            current_section.append(
                f'<h3 class="brief-block__sub" id="{sid}">{inline_markdown(sub)}</h3>'
            )
            i += 1
            continue

        if is_table_row(stripped):
            ensure_section()
            close_list()
            table_html, consumed = parse_table(lines[i:])
            if table_html:
                current_section.append(table_html)
                i += consumed
                continue

        if re.match(r"^[-*]\s+", stripped):
            ensure_section()
            if not in_list:
                current_section.append("<ul>")
                in_list = True
            item = re.sub(r"^[-*]\s+", "", stripped)
            current_section.append(f"<li>{inline_markdown(item)}</li>")
            i += 1
            continue

        ensure_section()
        close_list()
        if stripped.startswith("# "):
            i += 1
            continue
        current_section.append(f"<p>{inline_markdown(stripped)}</p>")
        i += 1

    flush_section()
    if not chunks:
        return '<section class="brief-block reveal" data-reveal></section>'
    return "\n\n        ".join(chunks)


def render_article_body(brief: Brief) -> str:
    if brief.body_format == "html":
        return brief.body_md.strip()
    return markdown_body_to_html(brief.body_md)


def document_title(brief: Brief) -> str:
    if brief.page_title:
        return brief.page_title
    base = brief.og_title or brief.title
    suffix = " — The San Jose Source"
    if base.endswith(suffix):
        return base
    return f"{base}{suffix}"


def social_description(brief: Brief) -> str:
    return brief.og_description or brief.description


def attr_escape(value: str) -> str:
    """Escape for double-quoted HTML attributes (matches existing site entity style)."""
    return html.escape(value, quote=True).replace("&#x27;", "&#39;")


def json_ld(brief: Brief) -> str:
    data: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": brief.title,
        "datePublished": brief.date.strftime("%Y-%m-%d"),
    }
    if brief.date_modified:
        data["dateModified"] = brief.date_modified.strftime("%Y-%m-%d")
    data["mainEntityOfPage"] = brief.canonical_url
    data["image"] = [f"{SITE_BASE}/assets/og.jpg"]
    data["author"] = {
        "@type": "Person",
        "name": brief.author,
        "url": f"{SITE_BASE}/about/",
    }
    data["publisher"] = {
        "@type": "Organization",
        "name": "The San Jose Source",
        "url": f"{SITE_BASE}/",
        "logo": {
            "@type": "ImageObject",
            "url": f"{SITE_BASE}/assets/logo.png",
        },
    }
    return json.dumps(data, indent=6, ensure_ascii=False)


def sort_briefs_newest_first(briefs: list[Brief]) -> list[Brief]:
    return sorted(briefs, key=lambda b: (b.sort_date, b.number), reverse=True)


def render_brief_page(brief: Brief) -> str:
    og_title = brief.og_title or brief.title
    page_title = document_title(brief)
    desc_attr = attr_escape(brief.description)
    desc_og = attr_escape(social_description(brief))
    title_class = "brief__title brief__title--long" if len(brief.title) > 60 else "brief__title"
    dek_html = ""
    if brief.dek:
        dek_html = f'\n        <p class="brief__dek reveal" data-reveal>{inline_markdown(brief.dek)}</p>'
    body_html = render_article_body(brief)
    byline = brief.meta_line if brief.meta_line else f"By {brief.author}"
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(page_title)}</title>
    <meta
      name="description"
      content="{desc_attr}"
    />
    <link rel="canonical" href="{brief.canonical_url}" />
    <link rel="icon" href="../../favicon.ico" sizes="any" />
    <link rel="icon" href="../../assets/favicon-32.png" type="image/png" sizes="32x32" />
    <link rel="icon" href="../../assets/icon-192.png" type="image/png" sizes="192x192" />
    <link rel="apple-touch-icon" href="../../assets/apple-touch-icon.png" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap"
      rel="stylesheet"
    />
    <link rel="stylesheet" href="../../styles.css" />
    <link
      rel="alternate"
      type="application/rss+xml"
      title="The San Jose Source RSS Feed"
      href="https://thesanjosesource.com/feed.xml"
    />
    <meta property="og:site_name" content="The San Jose Source" />
    <meta property="og:title" content="{html.escape(og_title, quote=True)}" />
    <meta property="og:description" content="{desc_og}" />
    <meta property="og:url" content="{brief.canonical_url}" />
    <meta property="og:type" content="{html.escape(brief.og_type, quote=True)}" />
    <meta property="og:image" content="{SITE_BASE}/assets/og.jpg" />
    <meta property="og:image:width" content="1280" />
    <meta property="og:image:height" content="720" />
    <meta property="og:image:alt" content="The San Jose Source: City money, before the vote." />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:site" content="@SanJoseSource" />
    <meta name="twitter:title" content="{html.escape(og_title, quote=True)}" />
    <meta name="twitter:description" content="{desc_og}" />
    <meta name="twitter:image" content="{SITE_BASE}/assets/og.jpg" />
    <meta name="twitter:image:alt" content="The San Jose Source: City money, before the vote." />
    <script type="application/ld+json">
{json_ld(brief)}
    </script>
</head>
  <body class="page-brief">
    <a class="skip" href="#main">Skip to content</a>
    <header class="topbar">
      <nav class="nav nav--light" aria-label="Primary">
        <a class="nav__brand" href="../../">The San Jose Source</a>
        <div class="nav__links">
          <a class="nav__link" href="../../#coverage">Briefs</a>
          <a class="nav__link" href="../../tracker/">Promised vs. Actual</a>
          <a class="nav__link" href="../../about/">About</a>
          <a class="nav__link" href="../../#subscribe">Subscribe</a>
        </div>
      </nav>
    </header>
    <main id="main" class="brief">
      <article class="wrap wrap--reading wrap--wide">
        <p class="eyebrow reveal" data-reveal>{html.escape(brief.default_eyebrow())}</p>
        <h1 class="{title_class} reveal" data-reveal>{html.escape(brief.title)}</h1>{dek_html}
        <p class="brief__meta reveal" data-reveal>{html.escape(byline)}</p>

        {body_html}

        <p class="brief__signoff reveal" data-reveal>— {html.escape(brief.author)}</p>
        <div class="brief__cta reveal" data-reveal>
          <a class="btn btn--gold" href="https://thesanjosesource.substack.com/subscribe" target="_blank" rel="noopener noreferrer">Subscribe free</a>
          <a class="btn btn--outline" href="../../">Back to home</a>
        </div>
      </article>
    </main>
    <footer class="footer">
      <div class="wrap footer__inner">
        <p class="footer__brand">The San Jose Source</p>
        <p class="footer__by">By J Gonzales · Nonpartisan · Record-linked</p>
        <p class="footer__by">
          <a href="https://thesanjosesource.com/">www.TheSanJoseSource.com</a>
        </p>
        <p class="footer__links">
          <a href="mailto:thesanjosesource@gmail.com">thesanjosesource@gmail.com</a>
          ·
          <a href="https://x.com/SanJoseSource" target="_blank" rel="noopener noreferrer">@SanJoseSource</a>
          ·
          <a href="https://thesanjosesource.substack.com" target="_blank" rel="noopener noreferrer">Substack</a> · <a href="https://buy.stripe.com/3cIfZi93P9ledEieEhasg00" target="_blank" rel="noopener noreferrer">Support</a>
        </p>
      </div>
    </footer>
    <script src="../../app.js" defer></script>
  </body>
</html>
"""


def write_brief_pages(briefs: Iterable[Brief]) -> None:
    for brief in briefs:
        out_dir = ROOT / "brief" / str(brief.number)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        out_path.write_text(render_brief_page(brief), encoding="utf-8", newline="\n")
        print(f"Wrote {out_path.relative_to(ROOT)}")


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    if start not in text or end not in text:
        raise ValueError(f"Missing build markers: {start!r} … {end!r}")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return before + start + replacement + end + after


def render_coverage_block(sorted_briefs: list[Brief]) -> str:
    latest, *archive = sorted_briefs
    latest_url = f"/brief/{latest.number}/"
    featured = textwrap.dedent(
        f"""
          <div class="section__lede reveal" data-reveal>
            <p>
              <a href="{latest_url}"><strong>{html.escape(latest.title)}</strong></a>
            </p>
            <p class="coverage__label">{html.escape(latest.default_coverage_label())}</p>
            <p>{html.escape(latest.default_homepage_blurb())}</p>
          </div>
        """
    ).rstrip()
    if not archive:
        archive_html = ""
    else:
        items = []
        for brief in archive:
            url = f"/brief/{brief.number}/"
            items.append(
                f"""            <li>
              <a href="{url}"><strong>{html.escape(brief.title)}</strong></a><br />
              <span class="coverage__label">{html.escape(brief.default_coverage_label())}</span><br />
              {html.escape(brief.default_homepage_blurb())}
            </li>"""
            )
        archive_html = (
            '\n          <h3 class="section__title reveal" data-reveal style="font-size: 1.25rem; margin-top: 2rem;">Earlier briefs</h3>\n'
            '          <ul class="section__lede reveal" data-reveal>\n'
            + "\n".join(items)
            + "\n          </ul>"
        )
    return (
        "\n          "
        + featured.strip().replace("\n", "\n          ")
        + archive_html
        + "\n          "
    )


def render_hero_latest(latest: Brief) -> str:
    url = f"/brief/{latest.number}/"
    return f'\n          <a class="btn btn--gold" href="{url}">Latest brief</a>\n          '


def update_index(briefs: list[Brief]) -> None:
    index_path = ROOT / "index.html"
    text = index_path.read_text(encoding="utf-8")
    sorted_briefs = sort_briefs_newest_first(briefs)
    text = replace_between(
        text,
        MARKER_COVERAGE_START,
        MARKER_COVERAGE_END,
        render_coverage_block(sorted_briefs),
    )
    text = replace_between(
        text,
        MARKER_HERO_START,
        MARKER_HERO_END,
        render_hero_latest(sorted_briefs[0]),
    )
    index_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Updated {index_path.relative_to(ROOT)}")


def discover_brief_urls_on_disk() -> list[str]:
    urls: list[str] = []
    brief_root = ROOT / "brief"
    if not brief_root.is_dir():
        return urls
    numbers = []
    for child in brief_root.iterdir():
        if child.is_dir() and child.name.isdigit() and (child / "index.html").is_file():
            numbers.append(int(child.name))
    for n in sorted(numbers):
        urls.append(f"{SITE_BASE}/brief/{n}/")
    return urls


def write_sitemap(brief_urls: list[str]) -> None:
    static = [
        f"{SITE_BASE}/",
        f"{SITE_BASE}/tracker/",
        f"{SITE_BASE}/about/",
    ]
    all_urls = static + brief_urls
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for loc in all_urls:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = loc
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    out = ROOT / "sitemap.xml"
    tree.write(out, encoding="UTF-8", xml_declaration=True)
    print(f"Wrote {out.relative_to(ROOT)}")


def rss_description(brief: Brief) -> str:
    return html.escape(brief.default_homepage_blurb())


def write_feed(briefs: list[Brief]) -> None:
    sorted_briefs = sort_briefs_newest_first(briefs)
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    for brief in sorted_briefs:
        pub = brief.date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        items.append(
            f"""    <item>
      <title>{html.escape(brief.title)}</title>
      <link>{brief.canonical_url}</link>
      <guid isPermaLink="true">{brief.canonical_url}</guid>
      <pubDate>{pub}</pubDate>
      <description>{rss_description(brief)}</description>
    </item>"""
        )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The San Jose Source</title>
    <link>{SITE_BASE}/</link>
    <description>San José decisions, public money, and what happens next.</description>
    <language>en-us</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    out = ROOT / "feed.xml"
    out.write_text(feed, encoding="utf-8", newline="\n")
    print(f"Wrote {out.relative_to(ROOT)}")


def main() -> int:
    try:
        briefs = discover_briefs()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not briefs:
        print(
            "No brief markdown found in content/ (expected brief-N.md). "
            "Skipping HTML and index updates."
        )
        write_sitemap(discover_brief_urls_on_disk())
        return 0

    write_brief_pages(briefs)
    update_index(briefs)
    write_feed(briefs)
    write_sitemap(discover_brief_urls_on_disk())
    print(f"Built {len(briefs)} brief(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
