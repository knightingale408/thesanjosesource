"""Record pages ask the fixed questions and show the official title."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "render_records", Path(__file__).resolve().parents[1] / "scripts" / "render_records.py"
)
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)

lib_spec = importlib.util.spec_from_file_location(
    "record_lib_pages", Path(__file__).resolve().parents[1] / "scripts" / "record_lib.py"
)
lib = importlib.util.module_from_spec(lib_spec)
lib_spec.loader.exec_module(lib)


def test_front_matter_round_trip_keeps_colons_and_quotes():
    title = 'Retroactive Approval of “Free Use”: plazas, 2.8'
    text = lib.dump_record({"kind": "item", "title": title, "file": "26-1183"})
    assert lib.load_record(text)["title"] == title


def test_item_and_meeting_pages_use_the_fixed_headings(tmp_path: Path):
    as_of = "2026-11-26T05:09:00-08:00"
    title = (
        "Retroactive Approval of “Free Use” of the City Hall East and West Plazas "
        "and the Janet Gray Hayes Rotunda for the Tunnel of Terror Event."
    )
    item = {
        "kind": "item",
        "file": "26-1183",
        "meeting": "2026-11-17",
        "section": "Consent Agenda",
        "state": "Outcome not posted",
        "agenda_number": "2.8",
        "matter_status": "Agenda Ready",
        "title": title,
        "legistar_url": "https://sanjose.legistar.com/LegislationDetail.aspx?ID=8307101&GUID=8E675B70-06CB-4536-899A-9BB198C253D4",
        "agenda_pdf": "https://legistar.granicus.com/sanjose/meetings/2026/11/8124_A.pdf",
        "minutes_pdf": "",
        "as_of": as_of,
        "amended": "",
        "memo_pdf": "https://legistar.granicus.com/sanjose/attachments/memo.pdf",
        "memo_from": "Jen Baker",
        "recommendation": "Adopt a resolution retroactively authorizing free use on October 24, 2026.",
        "fiscal_heading": "FISCAL IMPACTS",
        "fiscal": "The estimated total cost for the reservation is $6,708.60.",
        "update": "2026-11-25",
        "update_note": "Added the staff memorandum recommendation as a quote.",
        "attachments": [
            {"name": "Memorandum", "url": "https://legistar.granicus.com/sanjose/attachments/memo.pdf"},
        ],
    }
    meeting = {
        "kind": "meeting",
        "date": "2026-11-17",
        "body": "City Council",
        "state": "Outcome not posted",
        "legistar_url": "https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=8124&G=920296E4-80BE-4CA2-A78F-32C5EFCF78AF",
        "agenda_pdf": item["agenda_pdf"],
        "minutes_pdf": "",
        "as_of": as_of,
        "amended": "",
        "files": ["26-1183"],
    }
    (tmp_path / "content" / "items").mkdir(parents=True)
    (tmp_path / "content" / "meetings").mkdir(parents=True)
    (tmp_path / "content" / "items" / "26-1183.md").write_text(lib.dump_record(item), encoding="utf-8")
    (tmp_path / "content" / "meetings" / "2026-11-17.md").write_text(
        lib.dump_record(meeting), encoding="utf-8"
    )
    assert render.render_all(tmp_path, head_extras='    <meta name="referrer" content="strict-origin-when-cross-origin" />\n') == 4

    item_html = (tmp_path / "items" / "26-1183" / "index.html").read_text(encoding="utf-8")
    meeting_html = (tmp_path / "meetings" / "2026-11-17" / "index.html").read_text(encoding="utf-8")
    assert "<h1 class=\"brief__title reveal\" data-reveal>What is file 26-1183?</h1>" in item_html
    assert "What was on the San José City Council agenda for November 17, 2026?" in meeting_html
    assert title in item_html
    assert title in meeting_html
    assert 'data-state="Outcome not posted"' in item_html
    assert 'data-state="Outcome not posted"' in meeting_html
    assert "GUID=8E675B70-06CB-4536-899A-9BB198C253D4" in item_html
    assert "why it matters" not in item_html.lower()
    assert "why it matters" not in meeting_html.lower()
    assert "Memorandum (PDF)" in item_html
    assert "Minutes PDF" not in item_html
    assert "What the staff memo recommends" in item_html
    assert "Adopt a resolution retroactively authorizing free use on October 24, 2026." in item_html
    assert "$6,708.60" in item_html
    assert "$9,999" not in item_html
    assert "Not in the public record as of November 26, 2026, 5:09 a.m. Pacific." in item_html
    assert "<blockquote" in item_html
    assert (tmp_path / "items" / "index.html").is_file()
    assert (tmp_path / "meetings" / "index.html").is_file()
