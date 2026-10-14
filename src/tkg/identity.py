"""Speaker identity: link each Speaker label to a stable Person (HLD Section 6).

For now the PANEL line in each transcript is the source of truth.
Embedding-based matching for transcripts without a PANEL line comes later.
Anything we cannot resolve is flagged for a human, never guessed.
"""
from .models import Meeting, Person


def assign_people(meetings: list[Meeting]):
    """Fill person_id on every utterance.

    Returns:
        people:     {person_id: Person}
        unresolved: sorted list of (meeting_id, speaker_label) needing a human check
    """
    people: dict[str, Person] = {}
    unresolved: set[tuple[str, str]] = set()

    for meeting in meetings:
        for utt in meeting.utterances:
            person_id = meeting.panel.get(utt.speaker_label)
            if person_id is None:
                unresolved.add((meeting.meeting_id, utt.speaker_label))
                continue
            utt.person_id = person_id
            if person_id not in people:
                people[person_id] = Person(person_id=person_id, group=meeting.department)

    return people, sorted(unresolved)


if __name__ == "__main__":
    from .parser import load_transcripts

    meetings = load_transcripts()
    people, unresolved = assign_people(meetings)

    print("People found:")
    for p in people.values():
        print(" ", p.person_id, "-", p.group)
    print("Needs human check:", unresolved)

    print("\nEverything Person_001 said, across all meetings:")
    for m in meetings:
        for u in m.utterances:
            if u.person_id == "Person_001":
                print(" ", u.date, m.meeting_id, "-", u.text)