"""Offline page build: Agenda Ready + empty votes must not read as approved."""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import legistar_records as records


LEGISLATION = (
    "https://sanjose.legistar.com/LegislationDetail.aspx"
    "?ID=8307101&GUID=8E675B70-06CB-4536-899A-9BB198C253D4"
)
AGENDA = "https://legistar.granicus.com/sanjose/meetings/2026/11/agenda.pdf"
MEMO = "https://legistar.granicus.com/sanjose/attachments/memo.pdf"
ACTION_TEXT = "Adopt a resolution retroactively authorizing free use of the plazas."


def _raw(repo: Path, rel: str, payload: object) -> dict:
    data = json.dumps(payload).encode("utf-8")
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "url": "https://webapi.legistar.com/v1/sanjose/example"}


def _write_pull(repo: Path) -> None:
    event = {
        "EventId": 8124,
        "EventBodyName": "City Council",
        "EventDate": "2026-11-17T00:00:00",
        "EventTime": None,
        "EventLocation": "Council Chambers",
        "EventAgendaStatusName": "Final",
        "EventMinutesStatusName": "Draft",
        "EventMinutesFile": None,
        "EventAgendaFile": AGENDA,
        "EventInSiteURL": "https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=8124&GID=317&G=920296E4-80BE-4CA2-A78F-32C5EFCF78AF",
    }
    items = [
        {
            "EventItemId": 1,
            "EventItemAgendaSequence": 1,
            "EventItemTitle": "Language Access Instructions",
            "EventItemMatterFile": "26-602",
            "EventItemMatterId": 11,
            "EventItemMatterStatus": "Agenda Ready",
            "EventItemMatterType": "Consent Agenda",
            "EventItemActionName": None,
            "EventItemActionText": "drop me",
        },
        {
            "EventItemId": 2,
            "EventItemAgendaSequence": 2,
            "EventItemAgendaNumber": "2.8",
            "EventItemTitle": "Retroactive Approval of “Free Use” of the City Hall East and West Plazas and the Janet Gray Hayes Rotunda for the Tunnel of Terror Event.",
            "EventItemMatterFile": "26-1183",
            "EventItemMatterId": 16462,
            "EventItemMatterStatus": "Agenda Ready",
            "EventItemMatterType": "Consent Agenda",
            "EventItemActionName": None,
            "EventItemActionText": ACTION_TEXT,
        },
        {
            "EventItemId": 3,
            "EventItemAgendaSequence": 3,
            "EventItemTitle": "CEREMONIAL ITEMS",
            "EventItemMatterFile": None,
            "EventItemMatterId": None,
        },
        {
            "EventItemId": 4,
            "EventItemAgendaSequence": 4,
            "EventItemAgendaNumber": "2.1",
            "EventItemTitle": "Approval of City Council Minutes.",
            "EventItemMatterFile": "26-1213",
            "EventItemMatterId": 12,
            "EventItemMatterStatus": "Agenda Ready",
            "EventItemActionName": None,
        },
    ]
    attachments = [
        {
            "MatterAttachmentId": 40773,
            "MatterAttachmentName": "Memorandum",
            "MatterAttachmentHyperlink": MEMO,
            "MatterAttachmentShowOnInternetPage": True,
            "MatterAttachmentSort": 1,
        }
    ]
    events_rec = _raw(repo, "data/raw/sanjose/2026-11-17/events.json", [event])
    items_rec = _raw(repo, "data/raw/sanjose/2026-11-17/event-8124-items.json", items)
    att_rec = _raw(repo, "data/raw/sanjose/2026-11-17/matter-16462-attachments.json", attachments)
    votes_rec = _raw(repo, "data/raw/sanjose/2026-11-17/eventitem-2-votes.json", [])
    # Boilerplate matters still have raw vote files when a real pull saved them.
    # This fixture only needs the kept item's votes plus the files the index names.
    pull = {
        "body": "City Council",
        "client": "sanjose",
        "event_ids": {
            "8124": {
                "attachments": {"16462": att_rec},
                "event_items": items_rec,
                "votes": {"2": votes_rec},
            }
        },
        "files": {"events": events_rec},
        "legislation_urls": {
            "16462": {"resolved": True, "url": LEGISLATION},
        },
        "meeting_date": "2026-11-17",
        "pulled_at": "2026-11-26T05:40:12Z",
        "since": "2026-11-17",
        "until": "2026-11-17",
    }
    path = repo / "data" / "pulls" / "2026-11-17.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pull), encoding="utf-8")


def test_build_publishes_outcome_not_posted_and_keeps_the_title(tmp_path):
    _write_pull(tmp_path)
    assert records.build_repo(tmp_path) == 0
    assert records.build_repo(tmp_path, check=True) == 0

    item = (tmp_path / "items" / "26-1183" / "index.html").read_text(encoding="utf-8")
    meeting = (tmp_path / "meetings" / "2026-11-17" / "index.html").read_text(encoding="utf-8")
    assert "What is file 26-1183?" in item
    assert "Outcome not posted" in item
    assert "Agenda Ready" in item
    assert "Tunnel of Terror" in item
    assert "Consent Agenda" in item
    assert "LegislationDetail.aspx?ID=8307101&amp;GUID=8E675B70-06CB-4536-899A-9BB198C253D4" in item
    assert MEMO in item
    assert AGENDA in item
    assert "As of" in item
    assert ACTION_TEXT not in item
    assert re.search(r"\bapproved\b", item, re.I) is None
    assert re.search(r"\badopted\b", item, re.I) is None
    assert re.search(r"\bdenied\b", item, re.I) is None
    assert not (tmp_path / "items" / "26-602" / "index.html").exists()
    assert not (tmp_path / "items" / "26-1213" / "index.html").exists()

    assert "What was on the San José City Council agenda for November 17, 2026?" in meeting
    assert "26-1183" in meeting
    assert "Language Access" not in meeting
    assert "26-602" not in meeting
    assert records.lint_outputs(
        {
            "items/26-1183/index.html": item,
            "meetings/2026-11-17/index.html": meeting,
        }
    ) == []

    manifest = json.loads((tmp_path / "data" / "manifest.json").read_text(encoding="utf-8"))
    paths = {row["path"]: row for row in manifest["pages"]}
    assert paths["/items/26-1183/"]["state"] == "Outcome not posted"
    assert paths["/items/26-1183/"]["legislation_url"] == LEGISLATION
    assert paths["/items/26-1183/"]["pulled_at"] == "2026-11-26T05:40:12Z"
    assert paths["/meetings/2026-11-17/"]["state"] == "Outcome not posted"
    summary = manifest["meetings"][0]
    assert summary["kept"] == 1
    assert summary["dropped_boilerplate"] == 2


def test_action_name_renders_as_recorded_without_inventing_a_sentence(tmp_path):
    _write_pull(tmp_path)
    items_path = tmp_path / "data/raw/sanjose/2026-11-17/event-8124-items.json"
    items = json.loads(items_path.read_text(encoding="utf-8"))
    items[1]["EventItemActionName"] = "Approved"
    data = json.dumps(items).encode("utf-8")
    items_path.write_bytes(data)
    pull_path = tmp_path / "data" / "pulls" / "2026-11-17.json"
    pull = json.loads(pull_path.read_text(encoding="utf-8"))
    pull["event_ids"]["8124"]["event_items"]["sha256"] = hashlib.sha256(data).hexdigest()
    pull_path.write_text(json.dumps(pull), encoding="utf-8")

    assert records.build_repo(tmp_path) == 0
    item = (tmp_path / "items" / "26-1183" / "index.html").read_text(encoding="utf-8")
    assert 'data-record-state="Recorded"' in item
    assert 'data-record-field="action_name">Approved' in item
    assert "The Council approved" not in item
    assert records.lint_html(item, label="item") == []


def test_raw_hash_mismatch_stops_the_build(tmp_path):
    _write_pull(tmp_path)
    events = tmp_path / "data/raw/sanjose/2026-11-17/events.json"
    events.write_bytes(events.read_bytes() + b" ")
    with pytest.raises(SystemExit, match="edited after the pull"):
        records.build_repo(tmp_path)
