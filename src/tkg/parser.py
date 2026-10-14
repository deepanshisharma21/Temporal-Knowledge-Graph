"""Parser: turns one transcript's text into a Meeting."""
import datetime as dt
from pathlib import Path

from .models import Meeting, Utterance


def parse_transcript(text: str) -> Meeting:
    lines = text.strip().splitlines()

    # 1. Read the header (everything above the '---' line)
    header: dict[str, str] = {}
    body_start = None
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
        if ":" in line:
            key, _, value = line.partition(":")
            header[key.strip().upper()] = value.strip()

    if body_start is None:
        raise ValueError("Transcript has no '---' line between header and speech")
    for required in ("MEETING", "DATE", "DEPARTMENT"):
        if required not in header:
            raise ValueError(f"Transcript header is missing {required}")

    meeting_date = dt.date.fromisoformat(header["DATE"])

    candidate = header.get("CANDIDATE", "").strip()
    candidate_id = None if candidate.lower() in ("", "none") else candidate

    panel: dict[str, str] = {}
    for pair in header.get("PANEL", "").split(","):
        if "=" in pair:
            label, _, person_id = pair.partition("=")
            panel[label.strip()] = person_id.strip()

    meeting = Meeting(
        meeting_id=header["MEETING"],
        date=meeting_date,
        department=header["DEPARTMENT"],
        candidate_id=candidate_id,
        panel=panel,
    )

    # 2. Read the spoken lines (everything below the '---' line)
    index = 0
    for line in lines[body_start:]:
        line = line.strip()
        if not line:
            continue
        label, _, speech = line.partition(":")
        if not label.strip().startswith("Speaker"):
            raise ValueError(f"Cannot read this line in {meeting.meeting_id}: {line}")
        meeting.utterances.append(
            Utterance(
                meeting_id=meeting.meeting_id,
                index=index,
                speaker_label=label.strip(),
                text=speech.strip(),
                date=meeting_date,
            )
        )
        index += 1

    return meeting


def load_transcripts(folder: str = "data/transcripts") -> list[Meeting]:
    """Parse every .txt file in the folder, oldest meeting first."""
    meetings = [
        parse_transcript(path.read_text(encoding="utf-8"))
        for path in sorted(Path(folder).glob("*.txt"))
    ]
    return sorted(meetings, key=lambda m: m.date)


if __name__ == "__main__":
    for m in load_transcripts():
        print(m.date, m.meeting_id, m.department,
              "candidate =", m.candidate_id, "| lines =", len(m.utterances))