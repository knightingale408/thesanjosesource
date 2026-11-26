#!/usr/bin/env python3
"""Render content/meetings and content/items into static pages.

build.py calls render_all(). Pages use the site's existing classes in styles.css.
v1 shows the official title as Legistar returned it. It does not paraphrase.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_lib import (  # noqa: E402
    amended_label,
    format_as_of,
    load_record,
    long_date,
    parse_iso_date,
)

SITE_BASE = "https://thesanjosesource.com"
FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap"
)


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def fill(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", value)
    leftover = template.find("{{")
    if leftover != -1:
        raise RuntimeError(f"Unfilled template slot near {template[leftover:leftover + 40]!r}")
    return template


def load_dir(directory: Path) -> list[dict]:
    if not directory.is_dir():
        return []
    records = []
    for path in sorted(directory.glob("*.md")):
        fields = load_record(path.read_text(encoding="utf-8"))
        fields["_path"] = path
        records.append(fields)
    return records


def prefix(depth: int) -> str:
    return "../" * depth


def nav(depth: int) -> str:
    root = prefix(depth)
    return f"""<header class="topbar">
      <nav class="nav nav--light" aria-label="Primary">
        <a class="nav__brand" href="{root}">The San Jose Source</a>
        <div class="nav__links">
          <a class="nav__link" href="{root}#coverage">Briefs</a>
          <a class="nav__link" href="{root}tracker/">Promised vs. Actual</a>
          <a class="nav__link" href="{root}about/">About</a>
          <a class="nav__link" href="{root}#subscribe">Subscribe</a>
        </div>
      </nav>
    </header>"""


def footer() -> str:
    return """<footer class="footer">
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
    </footer>"""


def external(url: str, label: str) -> str:
    if not url:
        return ""
    return (
        f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'
    )


def shell(
    *,
    depth: int,
    title: str,
    description: str,
    canonical_path: str,
    heading: str,
    eyebrow: str,
    meta: str,
    body: str,
    state: str,
    head_extras: str,
    wide: bool,
) -> str:
    root = prefix(depth)
    canonical = f"{SITE_BASE}{canonical_path}"
    title_class = "brief__title brief__title--long" if len(heading) > 60 else "brief__title"
    wrap = "wrap wrap--reading wrap--wide" if wide else "wrap wrap--reading"
    state_attr = f' data-state="{esc(state)}"' if state else ""
    extras = head_extras if head_extras.endswith("\n") or not head_extras else head_extras + "\n"
    return fill(
        """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{TITLE}}</title>
    <meta
      name="description"
      content="{{DESCRIPTION}}"
    />
    <link rel="canonical" href="{{CANONICAL}}" />
    <link rel="icon" href="{{ROOT}}favicon.ico" sizes="any" />
    <link rel="icon" href="{{ROOT}}assets/favicon-32.png" type="image/png" sizes="32x32" />
    <link rel="icon" href="{{ROOT}}assets/icon-192.png" type="image/png" sizes="192x192" />
    <link rel="apple-touch-icon" href="{{ROOT}}assets/apple-touch-icon.png" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="{{FONTS}}"
      rel="stylesheet"
    />
    <link rel="stylesheet" href="{{ROOT}}styles.css" />
    <link
      rel="alternate"
      type="application/rss+xml"
      title="The San Jose Source RSS Feed"
      href="https://thesanjosesource.com/feed.xml"
    />
    <meta property="og:site_name" content="The San Jose Source" />
    <meta property="og:title" content="{{OG_TITLE}}" />
    <meta property="og:description" content="{{DESCRIPTION}}" />
    <meta property="og:url" content="{{CANONICAL}}" />
    <meta property="og:type" content="website" />
    <meta property="og:image" content="https://thesanjosesource.com/assets/og.jpg" />
    <meta property="og:image:width" content="1280" />
    <meta property="og:image:height" content="720" />
    <meta property="og:image:alt" content="The San Jose Source: City money, before the vote." />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:site" content="@SanJoseSource" />
    <meta name="twitter:title" content="{{OG_TITLE}}" />
    <meta name="twitter:description" content="{{DESCRIPTION}}" />
    <meta name="twitter:image" content="https://thesanjosesource.com/assets/og.jpg" />
    <meta name="twitter:image:alt" content="The San Jose Source: City money, before the vote." />
    <meta name="theme-color" content="#0f4c5c" />
{{HEAD_EXTRAS}}</head>
  <body class="page-brief"{{STATE_ATTR}}>
    <a class="skip" href="#main">Skip to content</a>
    {{NAV}}
    <main id="main" class="brief">
      <article class="{{WRAP}}">
        <p class="eyebrow reveal" data-reveal>{{EYEBROW}}</p>
        <h1 class="{{TITLE_CLASS}} reveal" data-reveal>{{HEADING}}</h1>
        <p class="brief__meta reveal" data-reveal>{{META}}</p>
        {{BODY}}
      </article>
    </main>
    {{FOOTER}}
    <script src="{{ROOT}}app.js" defer></script>
  </body>
</html>
""",
        TITLE=esc(title),
        DESCRIPTION=esc(description),
        CANONICAL=esc(canonical),
        ROOT=root,
        FONTS=FONTS,
        OG_TITLE=esc(heading),
        HEAD_EXTRAS=extras,
        STATE_ATTR=state_attr,
        NAV=nav(depth),
        WRAP=wrap,
        EYEBROW=esc(eyebrow),
        TITLE_CLASS=title_class,
        HEADING=esc(heading),
        META=esc(meta),
        BODY=body,
        FOOTER=footer(),
    )


def meta_line(record: dict) -> str:
    as_of = format_as_of(str(record.get("as_of") or ""))
    line = "By J Gonzales · From the public Legistar record"
    if as_of:
        line += f" · As of {as_of}"
    return line


def amended_html(record: dict) -> str:
    label = amended_label(str(record.get("amended") or ""))
    if not label:
        return ""
    return f'\n        <p class="brief__meta reveal" data-reveal>{esc(label)}</p>'


def quote_html(text: str) -> str:
    paragraphs = [part.strip() for part in str(text).split("\n\n") if part.strip()]
    inner = "\n".join(f"<p>{esc(part)}</p>" for part in paragraphs)
    return f'<blockquote class="memo-quote">\n{inner}\n</blockquote>'


def update_html(record: dict) -> str:
    note = str(record.get("update_note") or "").strip()
    if not note:
        return ""
    when = str(record.get("update") or "").strip()
    label = "Update"
    if when:
        try:
            shown = parse_iso_date(when).strftime("%b. %d, %Y").replace(" 0", " ")
            label = f"Update, {shown}"
        except ValueError:
            label = f"Update, {when}"
    return (
        '\n        <section class="brief-block brief-block--correction reveal" data-reveal '
        'aria-labelledby="updates-title">\n'
        '          <h2 id="updates-title" class="brief-block__title">Corrections and updates</h2>\n'
        f"          <p><strong>{esc(label)}.</strong> {esc(note)}</p>\n"
        "        </section>"
    )


def memo_html(record: dict) -> str:
    """Three boxes. The recommendation and fiscal text are quotes, not a rewrite."""
    memo_from = str(record.get("memo_from") or "").strip()
    recommendation = str(record.get("recommendation") or "").strip()
    fiscal = str(record.get("fiscal") or "").strip()
    memo_pdf = str(record.get("memo_pdf") or "").strip()
    as_of = format_as_of(str(record.get("as_of") or ""))
    state = str(record.get("state") or "")

    if recommendation:
        source = "From the staff memorandum"
        if memo_from:
            source += f", {memo_from}"
        if memo_pdf:
            recommend_body = (
                f"<p>{esc(source)}. {external(memo_pdf, 'Staff memorandum (PDF)')}.</p>\n"
                f"          {quote_html(recommendation)}"
            )
        else:
            recommend_body = f"<p>{esc(source)}.</p>\n          {quote_html(recommendation)}"
    elif memo_pdf:
        recommend_body = (
            "<p>No recommendation section was found in the "
            f"{external(memo_pdf, 'staff memorandum (PDF)')}.</p>"
        )
    else:
        recommend_body = "<p>No staff memorandum is in the public record for this file.</p>"

    if state == "Recorded":
        record_body = "<p>State: Recorded.</p>"
    elif as_of:
        record_body = f"<p>Not in the public record as of {esc(as_of)}.</p>"
    else:
        record_body = "<p>Not in the public record.</p>"

    if fiscal:
        heading = str(record.get("fiscal_heading") or "Fiscal section")
        change_body = (
            f"<p>The memorandum’s {esc(heading.lower())} section says:</p>\n"
            f"          {quote_html(fiscal)}"
        )
    else:
        change_body = "<p>The memo does not state a resident effect.</p>"

    return (
        '\n        <section class="brief-block reveal" data-reveal aria-labelledby="recommends-title">\n'
        '          <h2 id="recommends-title" class="brief-block__title">What the staff memo recommends</h2>\n'
        f"          {recommend_body}\n"
        "        </section>\n"
        '        <section class="brief-block reveal" data-reveal aria-labelledby="record-shows-title">\n'
        '          <h2 id="record-shows-title" class="brief-block__title">What the record shows</h2>\n'
        f"          {record_body}\n"
        "        </section>\n"
        '        <section class="brief-block reveal" data-reveal aria-labelledby="resident-title">\n'
        '          <h2 id="resident-title" class="brief-block__title">What changes for a resident</h2>\n'
        f"          {change_body}\n"
        "        </section>"
    )


def generated_line() -> str:
    return (
        '<p class="brief__meta reveal" data-reveal">'
        "This page is generated from the public Legistar record."
        "</p>"
    )


def write_page(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def item_map(items: list[dict]) -> dict[str, dict]:
    mapped: dict[str, dict] = {}
    for record in items:
        file_number = str(record.get("file") or "")
        if file_number:
            mapped[file_number] = record
    return mapped


def render_item(record: dict, *, depth: int, head_extras: str) -> str:
    file_number = str(record["file"])
    meeting = str(record.get("meeting") or "")
    heading = f"What is file {file_number}?"
    meeting_label = long_date(parse_iso_date(meeting)) if meeting else ""
    meeting_href = f"{prefix(depth)}meetings/{meeting}/" if meeting else ""
    rows = [
        ("File number", esc(file_number)),
        ("Official title", esc(record.get("title") or "")),
    ]
    if meeting and meeting_href:
        rows.append(
            (
                "Meeting",
                f'<a href="{esc(meeting_href)}">{esc(meeting_label)}</a>',
            )
        )
    if record.get("section"):
        rows.append(("Section", esc(record.get("section"))))
    if record.get("agenda_number"):
        rows.append(("Agenda number", esc(record.get("agenda_number"))))
    rows.append(("State", esc(record.get("state") or "")))
    if record.get("matter_status"):
        rows.append(("Legistar status", esc(record.get("matter_status"))))
    facts = "\n".join(
        f"          <p><strong>{esc(label)}.</strong> {value}</p>" for label, value in rows
    )
    links: list[str] = []
    if record.get("legistar_url"):
        links.append(f"<li>{external(str(record['legistar_url']), 'Legistar item')}</li>")
    if record.get("agenda_pdf"):
        links.append(f"<li>{external(str(record['agenda_pdf']), 'Agenda PDF')}</li>")
    for attachment in record.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        url = str(attachment.get("url") or "")
        if not url:
            continue
        name = str(attachment.get("name") or "Attachment")
        label = name if name.lower().endswith("pdf") else f"{name} (PDF)"
        links.append(f"<li>{external(url, label)}</li>")
    if record.get("minutes_pdf"):
        links.append(f"<li>{external(str(record['minutes_pdf']), 'Minutes PDF')}</li>")
    link_block = ""
    if links:
        link_block = (
            '\n        <section class="brief-block brief-block--sources reveal" data-reveal '
            'aria-labelledby="links-title">\n'
            '          <h2 id="links-title" class="brief-block__title">Official links</h2>\n'
            "          <ul>\n            "
            + "\n            ".join(links)
            + "\n          </ul>\n        </section>"
        )
    back = ""
    if meeting_href:
        back = (
            f'<a class="btn btn--outline" href="{esc(meeting_href)}">Meeting page</a>\n          '
        )
    body = f"""{amended_html(record)}{update_html(record)}
        <section class="brief-block reveal" data-reveal aria-labelledby="record-title">
          <h2 id="record-title" class="brief-block__title">Official record</h2>
{facts}
        </section>{memo_html(record)}{link_block}
        {generated_line()}
        <div class="brief__cta reveal" data-reveal>
          {back}<a class="btn btn--outline" href="{prefix(depth)}items/">All files</a>
        </div>"""
    description = (
        f"File {file_number}. Official title, meeting, section, state, and Legistar links. "
        "From the public Legistar record."
    )
    return shell(
        depth=depth,
        title=f"{heading} — The San Jose Source",
        description=description,
        canonical_path=f"/items/{file_number}/",
        heading=heading,
        eyebrow="City Council record",
        meta=meta_line(record),
        body=body,
        state=str(record.get("state") or ""),
        head_extras=head_extras,
        wide=False,
    )


def render_meeting(record: dict, items: dict[str, dict], *, depth: int, head_extras: str) -> str:
    meeting = str(record["date"])
    meeting_label = long_date(parse_iso_date(meeting))
    heading = f"What was on the San José City Council agenda for {meeting_label}?"
    links: list[str] = []
    if record.get("legistar_url"):
        links.append(f"<li>{external(str(record['legistar_url']), 'Legistar meeting')}</li>")
    if record.get("agenda_pdf"):
        links.append(f"<li>{external(str(record['agenda_pdf']), 'Agenda PDF')}</li>")
    if record.get("minutes_pdf"):
        links.append(f"<li>{external(str(record['minutes_pdf']), 'Minutes PDF')}</li>")
    link_html = ""
    if links:
        link_html = "<ul>\n            " + "\n            ".join(links) + "\n          </ul>"
    rows_html: list[str] = []
    for file_number in record.get("files") or []:
        item = items.get(str(file_number))
        if item is None:
            raise ValueError(f"Meeting {meeting} lists {file_number}, but content/items/{file_number}.md is missing")
        href = f"{prefix(depth)}items/{file_number}/"
        title = esc(item.get("title") or "")
        section = esc(item.get("section") or "")
        state = esc(item.get("state") or "")
        agenda = esc(item.get("agenda_number") or "")
        rows_html.append(
            "            <tr>\n"
            f"              <td>{agenda}</td>\n"
            f'              <td><a class="record-file" href="{esc(href)}">{esc(file_number)}</a></td>\n'
            f"              <td>{title}</td>\n"
            f"              <td>{section}</td>\n"
            f"              <td>{state}</td>\n"
            "            </tr>"
        )
    table = (
        '<div class="brief-table-wrap">\n'
        '          <table class="brief-table">\n'
        "            <thead>\n"
        "              <tr>\n"
        "                <th>Agenda</th>\n"
        "                <th>File</th>\n"
        "                <th>Official title</th>\n"
        "                <th>Section</th>\n"
        "                <th>State</th>\n"
        "              </tr>\n"
        "            </thead>\n"
        "            <tbody>\n"
        + "\n".join(rows_html)
        + "\n            </tbody>\n"
        "          </table>\n"
        "        </div>"
    )
    state = esc(record.get("state") or "")
    body = f"""{amended_html(record)}
        <section class="brief-block reveal" data-reveal aria-labelledby="meeting-links-title">
          <h2 id="meeting-links-title" class="brief-block__title">Official links</h2>
          <p><strong>State.</strong> {state}</p>
          {link_html}
        </section>
        <section class="brief-block reveal" data-reveal aria-labelledby="agenda-title">
          <h2 id="agenda-title" class="brief-block__title">Items on the agenda</h2>
          {table}
        </section>
        {generated_line()}
        <div class="brief__cta reveal" data-reveal>
          <a class="btn btn--outline" href="{prefix(depth)}meetings/">All meetings</a>
        </div>"""
    description = (
        f"Items on the San José City Council agenda for {meeting_label}, "
        "with each file number, official title, section, and state."
    )
    return shell(
        depth=depth,
        title=f"{heading} — The San Jose Source",
        description=description,
        canonical_path=f"/meetings/{meeting}/",
        heading=heading,
        eyebrow="City Council record",
        meta=meta_line(record),
        body=body,
        state=str(record.get("state") or ""),
        head_extras=head_extras,
        wide=True,
    )


def render_meeting_index(meetings: list[dict], *, head_extras: str) -> str:
    items_html = []
    ordered = sorted(meetings, key=lambda row: str(row.get("date") or ""), reverse=True)
    for record in ordered:
        meeting = str(record["date"])
        label = long_date(parse_iso_date(meeting))
        state = esc(record.get("state") or "")
        items_html.append(
            f'<li><a href="{esc(meeting)}/">{esc(label)}</a> — {state}</li>'
        )
    body = (
        '\n        <section class="brief-block reveal" data-reveal aria-labelledby="meetings-list-title">\n'
        '          <h2 id="meetings-list-title" class="brief-block__title">Meetings</h2>\n'
        "          <ul>\n            "
        + "\n            ".join(items_html)
        + "\n          </ul>\n        </section>\n        "
        + generated_line()
        + '\n        <div class="brief__cta reveal" data-reveal>\n'
        '          <a class="btn btn--outline" href="../items/">All files</a>\n'
        "        </div>"
    )
    as_of = ""
    if ordered:
        as_of = format_as_of(str(ordered[0].get("as_of") or ""))
    meta = "By J Gonzales · From the public Legistar record"
    if as_of:
        meta += f" · As of {as_of}"
    return shell(
        depth=1,
        title="San José City Council meetings — The San Jose Source",
        description="City Council meeting pages generated from the public Legistar record.",
        canonical_path="/meetings/",
        heading="San José City Council meetings",
        eyebrow="City Council record",
        meta=meta,
        body=body,
        state="",
        head_extras=head_extras,
        wide=False,
    )


def render_item_index(items: list[dict], *, head_extras: str) -> str:
    ordered = sorted(items, key=lambda row: str(row.get("file") or ""))
    rows = []
    for record in ordered:
        file_number = str(record.get("file") or "")
        title = esc(record.get("title") or "")
        state = esc(record.get("state") or "")
        meeting = str(record.get("meeting") or "")
        meeting_label = esc(long_date(parse_iso_date(meeting))) if meeting else ""
        rows.append(
            "            <tr>\n"
            f'              <td><a class="record-file" href="{esc(file_number)}/">{esc(file_number)}</a></td>\n'
            f"              <td>{title}</td>\n"
            f"              <td>{meeting_label}</td>\n"
            f"              <td>{state}</td>\n"
            "            </tr>"
        )
    table = (
        '<div class="brief-table-wrap">\n'
        '          <table class="brief-table">\n'
        "            <thead>\n"
        "              <tr><th>File</th><th>Official title</th><th>Meeting</th><th>State</th></tr>\n"
        "            </thead>\n"
        "            <tbody>\n"
        + "\n".join(rows)
        + "\n            </tbody>\n"
        "          </table>\n"
        "        </div>"
    )
    body = (
        '\n        <section class="brief-block reveal" data-reveal aria-labelledby="files-title">\n'
        '          <h2 id="files-title" class="brief-block__title">Files</h2>\n          '
        + table
        + "\n        </section>\n        "
        + generated_line()
        + '\n        <div class="brief__cta reveal" data-reveal>\n'
        '          <a class="btn btn--outline" href="../meetings/">All meetings</a>\n'
        "        </div>"
    )
    as_of = format_as_of(str(ordered[0].get("as_of") or "")) if ordered else ""
    meta = "By J Gonzales · From the public Legistar record"
    if as_of:
        meta += f" · As of {as_of}"
    return shell(
        depth=1,
        title="San José City Council files — The San Jose Source",
        description="One page per San José City Council file number, from the public Legistar record.",
        canonical_path="/items/",
        heading="San José City Council files",
        eyebrow="City Council record",
        meta=meta,
        body=body,
        state="",
        head_extras=head_extras,
        wide=True,
    )


def render_all(root: Path, head_extras: str = "") -> int:
    meetings = load_dir(root / "content" / "meetings")
    items = load_dir(root / "content" / "items")
    if not meetings and not items:
        print("No record markdown in content/meetings or content/items.")
        return 0
    by_file = item_map(items)
    count = 0
    for record in meetings:
        meeting = str(record["date"])
        out = root / "meetings" / meeting / "index.html"
        write_page(
            out,
            render_meeting(record, by_file, depth=2, head_extras=head_extras),
        )
        print(f"Wrote {out.relative_to(root)}")
        count += 1
    for record in items:
        file_number = str(record["file"])
        out = root / "items" / file_number / "index.html"
        write_page(out, render_item(record, depth=2, head_extras=head_extras))
        print(f"Wrote {out.relative_to(root)}")
        count += 1
    if meetings:
        out = root / "meetings" / "index.html"
        write_page(out, render_meeting_index(meetings, head_extras=head_extras))
        print(f"Wrote {out.relative_to(root)}")
        count += 1
    if items:
        out = root / "items" / "index.html"
        write_page(out, render_item_index(items, head_extras=head_extras))
        print(f"Wrote {out.relative_to(root)}")
        count += 1
    return count
