"""Fixed question functions (HLD Section 10).

Each function runs a ready-made graph query and returns the answer together
with the meeting and date it came from, so nothing is made up.
"""
from .db import get_driver


def _query(cypher: str, **params) -> list[dict]:
    driver = get_driver()
    try:
        with driver.session() as session:
            return [record.data() for record in session.run(cypher, **params)]
    finally:
        driver.close()


def _d(value):
    """Neo4j dates -> plain text like 2026-09-01."""
    return None if value is None else str(value)


def get_candidate_journey(candidate_id: str) -> list[dict]:
    """Every round for one candidate, oldest first, with panel and status then."""
    rows = _query(
        "MATCH (c:Candidate {candidate_id: $cid})<-[:IS_ABOUT]-(m:Meeting) "
        "OPTIONAL MATCH (c)-[:HAS_STATUS]->(s:StatusFact) "
        "  WHERE s.valid_from <= m.date AND (s.valid_to IS NULL OR m.date < s.valid_to) "
        "OPTIONAL MATCH (p:Person)-[:TOOK_PART_IN]->(m) "
        "RETURN m.meeting_id AS meeting_id, m.date AS date, "
        "       m.department AS department, "
        "       collect(DISTINCT p.person_id) AS panel, s.status AS status "
        "ORDER BY m.date",
        cid=candidate_id,
    )
    return [
        {"meeting_id": r["meeting_id"], "date": _d(r["date"]),
         "department": r["department"], "panel": sorted(r["panel"]),
         "status": r["status"]}
        for r in rows
    ]


def get_person_timeline(person_id: str) -> dict:
    """Everything one person said and every concern they raised, in date order."""
    said = _query(
        "MATCH (p:Person {person_id: $pid})-[:SAID]->(u:Utterance)"
        "<-[:HAS_UTTERANCE]-(m:Meeting) "
        "RETURN m.date AS date, m.meeting_id AS meeting_id, "
        "       m.department AS department, u.idx AS idx, u.text AS text "
        "ORDER BY m.date, u.idx",
        pid=person_id,
    )
    concerns = _query(
        "MATCH (p:Person {person_id: $pid})-[r:RAISED_CONCERN]->(t:Topic) "
        "RETURN r.date AS date, r.meeting_id AS meeting_id, t.label AS topic "
        "ORDER BY r.date",
        pid=person_id,
    )
    return {
        "person_id": person_id,
        "said": [{**r, "date": _d(r["date"])} for r in said],
        "concerns": [{**r, "date": _d(r["date"])} for r in concerns],
    }


def get_meeting(meeting_id: str) -> dict | None:
    """Who was in one meeting and what was said, line by line."""
    head = _query(
        "MATCH (m:Meeting {meeting_id: $mid}) "
        "OPTIONAL MATCH (m)-[:IS_ABOUT]->(c:Candidate) "
        "RETURN m.meeting_id AS meeting_id, m.date AS date, "
        "       m.department AS department, c.candidate_id AS candidate",
        mid=meeting_id,
    )
    if not head:
        return None
    attendees = _query(
        "MATCH (p:Person)-[:TOOK_PART_IN]->(:Meeting {meeting_id: $mid}) "
        "RETURN p.person_id AS person_id ORDER BY person_id",
        mid=meeting_id,
    )
    lines = _query(
        "MATCH (:Meeting {meeting_id: $mid})-[:HAS_UTTERANCE]->(u:Utterance) "
        "OPTIONAL MATCH (p:Person)-[:SAID]->(u) "
        "RETURN u.idx AS idx, p.person_id AS person_id, u.text AS text "
        "ORDER BY u.idx",
        mid=meeting_id,
    )
    h = head[0]
    return {
        "meeting_id": h["meeting_id"], "date": _d(h["date"]),
        "department": h["department"], "candidate": h["candidate"],
        "attendees": [a["person_id"] for a in attendees],
        "lines": lines,
    }


def _meeting_summary(meeting_id: str) -> dict | None:
    head = _query(
        "MATCH (m:Meeting {meeting_id: $mid}) RETURN m.date AS date", mid=meeting_id
    )
    if not head:
        return None
    status = _query(
        "MATCH (m:Meeting {meeting_id: $mid})-[:IS_ABOUT]->(c:Candidate)"
        "-[:HAS_STATUS]->(s:StatusFact) "
        "WHERE s.valid_from <= m.date AND (s.valid_to IS NULL OR m.date < s.valid_to) "
        "RETURN s.status AS status",
        mid=meeting_id,
    )
    topics = _query(
        "MATCH (:Meeting {meeting_id: $mid})-[:HAS_UTTERANCE]->(:Utterance)"
        "-[:ABOUT]->(t:Topic) RETURN DISTINCT t.label AS topic ORDER BY topic",
        mid=meeting_id,
    )
    concerns = _query(
        "MATCH (p:Person)-[r:RAISED_CONCERN {meeting_id: $mid}]->(t:Topic) "
        "RETURN t.label AS topic, collect(DISTINCT p.person_id) AS raised_by "
        "ORDER BY topic",
        mid=meeting_id,
    )
    return {
        "meeting_id": meeting_id,
        "date": _d(head[0]["date"]),
        "status": status[0]["status"] if status else None,
        "topics": [t["topic"] for t in topics],
        "concerns": {c["topic"]: sorted(c["raised_by"]) for c in concerns},
    }


def compare_meetings(meeting_a: str, meeting_b: str) -> dict | None:
    """What changed between two meetings: status, topics and concerns."""
    a = _meeting_summary(meeting_a)
    b = _meeting_summary(meeting_b)
    if a is None or b is None:
        return None
    if a["date"] > b["date"]:            # always compare older -> newer
        a, b = b, a
    same_series = bool(_query(
        "MATCH (:Meeting {meeting_id: $a})-[:PART_OF_SERIES]->(s)"
        "<-[:PART_OF_SERIES]-(:Meeting {meeting_id: $b}) RETURN s.name AS name",
        a=a["meeting_id"], b=b["meeting_id"],
    ))
    return {
        "earlier": a,
        "later": b,
        "same_series": same_series,
        "changes": {
            "status": None if a["status"] == b["status"]
                      else f"{a['status']} -> {b['status']}",
            "new_topics": sorted(set(b["topics"]) - set(a["topics"])),
            "dropped_topics": sorted(set(a["topics"]) - set(b["topics"])),
            "new_concerns": sorted(set(b["concerns"]) - set(a["concerns"])),
            "concerns_no_longer_raised":
                sorted(set(a["concerns"]) - set(b["concerns"])),
        },
    }


def find_cross_group_concerns(topic: str, start: str | None = None,
                              end: str | None = None) -> dict:
    """Who raised a concern about a topic, in which group, when, and where.
    start / end are optional dates like '2026-09-01'."""
    rows = _query(
        "MATCH (p:Person)-[r:RAISED_CONCERN]->(t:Topic {label: $topic}) "
        "WHERE ($start IS NULL OR r.date >= date($start)) "
        "  AND ($end IS NULL OR r.date <= date($end)) "
        "MATCH (p)-[:BELONGS_TO]->(g:Group) "
        "OPTIONAL MATCH (u:Utterance {uid: r.uid}) "
        "RETURN r.date AS date, g.name AS group, p.person_id AS person_id, "
        "       r.meeting_id AS meeting_id, u.text AS quote "
        "ORDER BY r.date, p.person_id",
        topic=topic, start=start, end=end,
    )
    raised = [{**r, "date": _d(r["date"])} for r in rows]
    return {
        "topic": topic,
        "groups": sorted({r["group"] for r in raised}),
        "raised": raised,
    }


def get_group_activity(group: str, start: str | None = None,
                       end: str | None = None) -> list[dict]:
    """Meetings a department had in a date range."""
    rows = _query(
        "MATCH (m:Meeting {department: $group}) "
        "WHERE ($start IS NULL OR m.date >= date($start)) "
        "  AND ($end IS NULL OR m.date <= date($end)) "
        "OPTIONAL MATCH (m)-[:IS_ABOUT]->(c:Candidate) "
        "OPTIONAL MATCH (p:Person)-[:TOOK_PART_IN]->(m) "
        "RETURN m.meeting_id AS meeting_id, m.date AS date, "
        "       c.candidate_id AS candidate, count(DISTINCT p) AS attendees "
        "ORDER BY m.date",
        group=group, start=start, end=end,
    )
    return [{**r, "date": _d(r["date"])} for r in rows]


def resolve_speaker(meeting_id: str, speaker_label: str) -> dict:
    """Which stable Person a speaker label maps to. If unsure, says so."""
    rows = _query(
        "MATCH (:Meeting {meeting_id: $mid})-[:HAS_UTTERANCE]->"
        "(u:Utterance {speaker_label: $label}) "
        "OPTIONAL MATCH (p:Person)-[:SAID]->(u) "
        "RETURN DISTINCT p.person_id AS person_id",
        mid=meeting_id, label=speaker_label,
    )
    ids = [r["person_id"] for r in rows if r["person_id"]]
    if not rows:
        status = "speaker_not_found"
    elif len(ids) == 1:
        status = "resolved"
    else:
        status = "needs_human_check"
    return {"meeting_id": meeting_id, "speaker_label": speaker_label,
            "person_id": ids[0] if len(ids) == 1 else None, "status": status}


if __name__ == "__main__":
    print("== get_candidate_journey('Candidate_01') ==")
    for r in get_candidate_journey("Candidate_01"):
        print(f"  {r['date']} {r['meeting_id']} ({r['department']}) "
              f"panel={r['panel']} status={r['status']}")

    print("\n== compare_meetings('HR_Round1', 'HR_Round2') ==")
    c = compare_meetings("HR_Round1", "HR_Round2")
    print(f"  {c['earlier']['meeting_id']} ({c['earlier']['date']}) -> "
          f"{c['later']['meeting_id']} ({c['later']['date']}), "
          f"same series: {c['same_series']}")
    for key, value in c["changes"].items():
        print(f"  {key}: {value}")

    print("\n== find_cross_group_concerns('communication skills') ==")
    f = find_cross_group_concerns("communication skills")
    print("  groups:", f["groups"])
    for r in f["raised"]:
        print(f"  {r['date']} {r['group']} {r['person_id']} "
              f"({r['meeting_id']}): {r['quote']}")

    print("\n== get_group_activity('HR', '2026-09-01', '2026-09-30') ==")
    for r in get_group_activity("HR", "2026-09-01", "2026-09-30"):
        print(f"  {r['date']} {r['meeting_id']} "
              f"candidate={r['candidate']} attendees={r['attendees']}")

    print("\n== resolve_speaker ==")
    print(" ", resolve_speaker("HR_Round2", "Speaker2"))
    print(" ", resolve_speaker("HR_Round1", "Speaker9"))