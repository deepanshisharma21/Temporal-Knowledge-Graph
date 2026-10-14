"""Write parsed meetings into Neo4j (HLD Section 5)."""
from .db import get_driver
from .identity import assign_people
from .models import Meeting, Person
from .parser import load_transcripts

CONSTRAINTS = [
    "CREATE CONSTRAINT group_name IF NOT EXISTS FOR (g:Group) REQUIRE g.name IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
    "CREATE CONSTRAINT meeting_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.meeting_id IS UNIQUE",
    "CREATE CONSTRAINT candidate_id IF NOT EXISTS FOR (c:Candidate) REQUIRE c.candidate_id IS UNIQUE",
    "CREATE CONSTRAINT utterance_uid IF NOT EXISTS FOR (u:Utterance) REQUIRE u.uid IS UNIQUE",
]


def _write_meeting(tx, meeting: Meeting, people: dict[str, Person]):
    iso = meeting.date.isoformat()

    tx.run(
        "MERGE (m:Meeting {meeting_id: $mid}) "
        "SET m.date = date($date), m.department = $dept",
        mid=meeting.meeting_id, date=iso, dept=meeting.department,
    )
    tx.run("MERGE (:Group {name: $dept})", dept=meeting.department)

    if meeting.candidate_id:
        tx.run(
            "MATCH (m:Meeting {meeting_id: $mid}) "
            "MERGE (c:Candidate {candidate_id: $cid}) "
            "MERGE (m)-[:IS_ABOUT]->(c)",
            mid=meeting.meeting_id, cid=meeting.candidate_id,
        )

    # People who took part in this meeting
    for person_id in set(meeting.panel.values()):
        person = people.get(person_id)
        if person is None:
            continue
        tx.run(
            "MATCH (m:Meeting {meeting_id: $mid}) "
            "MERGE (p:Person {person_id: $pid}) "
            "SET p.confidence = $conf "
            "MERGE (g:Group {name: $group}) "
            "MERGE (p)-[:BELONGS_TO]->(g) "
            "MERGE (p)-[r:TOOK_PART_IN]->(m) "
            "SET r.date = date($date)",
            mid=meeting.meeting_id, pid=person_id, conf=person.confidence,
            group=person.group, date=iso,
        )

    # What was said
    for utt in meeting.utterances:
        uid = f"{utt.meeting_id}#{utt.index}"
        tx.run(
            "MATCH (m:Meeting {meeting_id: $mid}) "
            "MERGE (u:Utterance {uid: $uid}) "
            "SET u.text = $text, u.idx = $idx, u.speaker_label = $label, "
            "    u.date = date($date) "
            "MERGE (m)-[:HAS_UTTERANCE]->(u)",
            mid=utt.meeting_id, uid=uid, text=utt.text, idx=utt.index,
            label=utt.speaker_label, date=iso,
        )
        if utt.person_id:
            tx.run(
                "MATCH (p:Person {person_id: $pid}), (u:Utterance {uid: $uid}) "
                "MERGE (p)-[r:SAID]->(u) "
                "SET r.date = date($date)",
                pid=utt.person_id, uid=uid, date=iso,
            )


def load_into_neo4j(meetings: list[Meeting]):
    people, unresolved = assign_people(meetings)
    driver = get_driver()
    with driver.session() as session:
        for statement in CONSTRAINTS:
            session.run(statement)
        for meeting in meetings:
            session.execute_write(_write_meeting, meeting, people)
    driver.close()
    return unresolved


def print_counts():
    driver = get_driver()
    with driver.session() as session:
        print("Nodes:")
        for r in session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS n ORDER BY label"
        ):
            print(f"  {r['label']}: {r['n']}")
        print("Relationships:")
        for r in session.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS n ORDER BY type"
        ):
            print(f"  {r['type']}: {r['n']}")
    driver.close()


if __name__ == "__main__":
    unresolved = load_into_neo4j(load_transcripts())
    print("Needs human check:", unresolved)
    print_counts()