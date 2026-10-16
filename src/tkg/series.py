"""Group meetings into series and link them in time order (HLD Sections 5.2 and 7)."""
import re

from .db import get_driver
from .graph import print_counts
from .models import Meeting
from .parser import load_transcripts


def series_name(meeting_id: str) -> str:
    """ASSUMPTION: 'HR_Round1' and 'HR_Round2' belong to series 'HR_Round'
    (the meeting name minus its trailing number). Change this rule if your
    real transcripts name meetings differently."""
    return re.sub(r"\d+$", "", meeting_id).rstrip("_- ")


def group_into_series(meetings: list[Meeting]) -> dict[str, list[Meeting]]:
    series: dict[str, list[Meeting]] = {}
    for m in meetings:
        series.setdefault(series_name(m.meeting_id), []).append(m)
    for members in series.values():
        members.sort(key=lambda m: m.date)
    return series


def _write(tx, series: dict[str, list[Meeting]]):
    for name, members in series.items():
        tx.run("MERGE (:MeetingSeries {name: $name})", name=name)
        for m in members:
            tx.run(
                "MATCH (m:Meeting {meeting_id: $mid}), (s:MeetingSeries {name: $name}) "
                "MERGE (m)-[:PART_OF_SERIES]->(s)",
                mid=m.meeting_id, name=name,
            )
        # each meeting points back to the one right before it
        for older, newer in zip(members, members[1:]):
            tx.run(
                "MATCH (n:Meeting {meeting_id: $newer}), (o:Meeting {meeting_id: $older}) "
                "MERGE (n)-[r:COMES_AFTER]->(o) SET r.date = date($date)",
                newer=newer.meeting_id, older=older.meeting_id,
                date=newer.date.isoformat(),
            )


if __name__ == "__main__":
    series = group_into_series(load_transcripts())
    driver = get_driver()
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT series_name IF NOT EXISTS "
            "FOR (s:MeetingSeries) REQUIRE s.name IS UNIQUE"
        )
        session.execute_write(_write, series)
    driver.close()

    print("Series:")
    for name, members in series.items():
        print(f"  {name}: " + " -> ".join(m.meeting_id for m in members))
    print()
    print_counts()