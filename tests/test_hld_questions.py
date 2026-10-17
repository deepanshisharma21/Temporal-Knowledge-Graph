"""Tests built from the example questions in HLD Section 12.

The database tests need Neo4j running with the three sample meetings loaded.
If Neo4j is not running they are skipped instead of failing.
"""
import pytest

from src.tkg.extraction import extract_utterance
from src.tkg.parser import parse_transcript


def _db_up() -> bool:
    try:
        from src.tkg.db import get_driver
        driver = get_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_up(), reason="Neo4j is not running")


# ---------- no database needed ----------

def test_parser_reads_header_and_lines():
    text = (
        "MEETING: M1\nDATE: 2026-01-02\nDEPARTMENT: HR\nCANDIDATE: none\n"
        "PANEL: Speaker1=Person_009\n---\nSpeaker1: Hello there."
    )
    m = parse_transcript(text)
    assert m.meeting_id == "M1"
    assert m.candidate_id is None
    assert m.panel == {"Speaker1": "Person_009"}
    assert len(m.utterances) == 1
    assert m.utterances[0].person_id is None      # filled in later, not by the parser


def test_parser_rejects_missing_separator():
    with pytest.raises(ValueError):
        parse_transcript("MEETING: M1\nDATE: 2026-01-02")


def test_extraction_concern_vs_no_concern():
    clear = extract_utterance("Communication was much clearer this time.")
    assert clear.topics == ["communication skills"]
    assert clear.concerns == []
    mixed = extract_utterance(
        "Agreed, communication was unclear. Technical skills look good though."
    )
    assert mixed.topics == ["communication skills", "technical skills"]
    assert mixed.concerns == ["communication skills"]


def test_extraction_status():
    assert extract_utterance("let us put the candidate on hold for now.").status == "on hold"
    assert extract_utterance("I recommend we move forward.").status == "move forward"
    assert extract_utterance("Tell us about your last project.").status is None


# ---------- HLD 12: simple lookup ----------

@needs_db
def test_simple_lookup_finds_right_line():
    from src.tkg.embeddings import search_topics
    top = search_topics("Who struggled to explain things clearly?")[0]
    assert top["meeting_id"] == "HR_Round1"
    assert "struggled" in top["text"]


@needs_db
def test_simple_lookup_respects_department():
    from src.tkg.embeddings import search_topics
    hits = search_topics("problems with how new people talk to the team",
                         department="Engineering")
    assert hits and all(h["meeting_id"] == "Eng_Sync1" for h in hits)


# ---------- HLD 12: counting ----------

@needs_db
def test_counting_rounds_and_panel():
    from src.tkg.queries import get_candidate_journey
    journey = get_candidate_journey("Candidate_01")
    assert len(journey) == 2
    people = {p for r in journey for p in r["panel"]}
    assert people == {"Person_001", "Person_002", "Person_003"}


@needs_db
def test_counting_group_meetings():
    from src.tkg.queries import get_group_activity
    assert len(get_group_activity("HR", "2026-09-01", "2026-09-30")) == 2


# ---------- HLD 12: what changed ----------

@needs_db
def test_what_changed_between_rounds():
    from src.tkg.queries import compare_meetings
    c = compare_meetings("HR_Round2", "HR_Round1")     # reversed on purpose
    assert c["earlier"]["meeting_id"] == "HR_Round1"
    assert c["same_series"] is True
    assert c["changes"]["status"] == "on hold -> move forward"
    assert c["changes"]["new_concerns"] == ["system design"]
    assert c["changes"]["concerns_no_longer_raised"] == ["communication skills"]


# ---------- HLD 12: across teams ----------

@needs_db
def test_across_teams_concerns():
    from src.tkg.queries import find_cross_group_concerns
    f = find_cross_group_concerns("communication skills")
    assert f["groups"] == ["Engineering", "HR"]
    assert len(f["raised"]) == 4


@needs_db
def test_across_teams_date_filter():
    from src.tkg.queries import find_cross_group_concerns
    f = find_cross_group_concerns("communication skills", start="2026-09-05")
    assert f["groups"] == ["Engineering"]
    assert {r["person_id"] for r in f["raised"]} == {"Person_004", "Person_005"}


# ---------- HLD 12: same person, different meetings ----------

@needs_db
def test_same_person_different_meetings():
    from src.tkg.queries import get_person_timeline
    t = get_person_timeline("Person_001")
    assert len(t["said"]) == 4
    assert {r["meeting_id"] for r in t["said"]} == {"HR_Round1", "HR_Round2"}


@needs_db
def test_resolve_speaker():
    from src.tkg.queries import resolve_speaker
    ok = resolve_speaker("HR_Round2", "Speaker2")
    assert ok["status"] == "resolved" and ok["person_id"] == "Person_003"
    assert resolve_speaker("HR_Round1", "Speaker9")["status"] == "speaker_not_found"