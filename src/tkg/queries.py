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


if __name__ == "__main__":
    print("== get_candidate_journey('Candidate_01') ==")
    for r in get_candidate_journey("Candidate_01"):
        print(f"  {r['date']} {r['meeting_id']} ({r['department']}) "
              f"panel={r['panel']} status={r['status']}")

    print("\n== get_person_timeline('Person_001') ==")
    t = get_person_timeline("Person_001")
    for r in t["said"]:
        print(f"  {r['date']} {r['meeting_id']}: {r['text']}")
    for r in t["concerns"]:
        print(f"  concern: {r['topic']} ({r['date']} {r['meeting_id']})")

    print("\n== get_meeting('HR_Round2') ==")
    m = get_meeting("HR_Round2")
    print(" ", m["date"], m["department"], "candidate =", m["candidate"],
          "attendees =", m["attendees"])
    for r in m["lines"]:
        print(f"  #{r['idx']} {r['person_id']}: {r['text']}")