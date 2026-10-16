"""Step 8b: write topics, concerns and status history into Neo4j (HLD Sections 5 and 7)."""
from .db import get_driver
from .extraction import Extraction, extract_all
from .graph import print_counts
from .identity import assign_people
from .models import Meeting, StatusFact
from .parser import load_transcripts

CONSTRAINTS = [
    "CREATE CONSTRAINT topic_label IF NOT EXISTS FOR (t:Topic) REQUIRE t.label IS UNIQUE",
    "CREATE CONSTRAINT status_fact_id IF NOT EXISTS FOR (s:StatusFact) REQUIRE s.fact_id IS UNIQUE",
]


def fact_id(fact: StatusFact) -> str:
    return f"{fact.subject_id}|{fact.status}|{fact.valid_from.isoformat()}"


def build_status_facts(meetings: list[Meeting],
                       results: dict[str, Extraction]) -> list[StatusFact]:
    """Turn the status said in each meeting into a timeline per candidate.

    Meetings must be in date order (load_transcripts does that). If the status
    is unchanged from the previous meeting, no new fact is created. If it
    changes, the old fact is closed (valid_to) and the new one points back to it.
    """
    facts: list[StatusFact] = []
    current: dict[str, StatusFact] = {}

    for meeting in meetings:
        cid = meeting.candidate_id
        if not cid:
            continue
        status = None
        for utt in meeting.utterances:                 # last status in the meeting wins
            ex = results[f"{utt.meeting_id}#{utt.index}"]
            if ex.status:
                status = ex.status
        if status is None:
            continue

        previous = current.get(cid)
        if previous and previous.status == status:
            continue

        fact = StatusFact(subject_id=cid, status=status, valid_from=meeting.date,
                          source_meeting_id=meeting.meeting_id)
        if previous:
            previous.valid_to = meeting.date
            fact.replaces = fact_id(previous)
        facts.append(fact)
        current[cid] = fact
    return facts


def _write(tx, meetings, results, facts):
    for meeting in meetings:
        for utt in meeting.utterances:
            uid = f"{utt.meeting_id}#{utt.index}"
            ex = results[uid]
            for label in ex.topics:
                tx.run(
                    "MATCH (u:Utterance {uid: $uid}) "
                    "MERGE (t:Topic {label: $label}) "
                    "MERGE (u)-[:ABOUT]->(t)",
                    uid=uid, label=label,
                )
            if utt.person_id:
                for label in ex.concerns:
                    tx.run(
                        "MATCH (p:Person {person_id: $pid}), (t:Topic {label: $label}) "
                        "MERGE (p)-[r:RAISED_CONCERN {uid: $uid}]->(t) "
                        "SET r.date = date($date), r.meeting_id = $mid",
                        pid=utt.person_id, label=label, uid=uid,
                        date=meeting.date.isoformat(), mid=meeting.meeting_id,
                    )

    for fact in facts:
        tx.run(
            "MERGE (s:StatusFact {fact_id: $fid}) "
            "SET s.status = $status, s.valid_from = date($vf), "
            "    s.valid_to = CASE WHEN $vt IS NULL THEN null ELSE date($vt) END "
            "WITH s "
            "MATCH (c:Candidate {candidate_id: $cid}) "
            "MERGE (c)-[:HAS_STATUS]->(s) "
            "WITH s "
            "MATCH (m:Meeting {meeting_id: $mid}) "
            "MERGE (s)-[:STATED_IN]->(m)",
            fid=fact_id(fact), status=fact.status, vf=fact.valid_from.isoformat(),
            vt=fact.valid_to.isoformat() if fact.valid_to else None,
            cid=fact.subject_id, mid=fact.source_meeting_id,
        )
        if fact.replaces:
            tx.run(
                "MATCH (new:StatusFact {fact_id: $new}), (old:StatusFact {fact_id: $old}) "
                "MERGE (new)-[:REPLACES]->(old)",
                new=fact_id(fact), old=fact.replaces,
            )


if __name__ == "__main__":
    meetings = load_transcripts()
    assign_people(meetings)
    results = extract_all(meetings)
    facts = build_status_facts(meetings, results)

    driver = get_driver()
    with driver.session() as session:
        for statement in CONSTRAINTS:
            session.run(statement)
        session.execute_write(_write, meetings, results, facts)
    driver.close()

    print("Status history:")
    for f in facts:
        print(f"  {f.subject_id}: {f.status} from {f.valid_from} to {f.valid_to or 'now'}")
    print()
    print_counts()