"""Data models for the Temporal Knowledge Graph project."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Utterance:
    """One spoken line in a meeting."""
    meeting_id: str      # e.g. "HR_Round1"
    index: int           # position of the line in the meeting (0, 1, 2...)
    speaker_label: str   # e.g. "Speaker1"
    person_id: str       # e.g. "Person_001" (looked up from the PANEL line)
    text: str            # what was said
    date: date           # copied from the meeting, so every line has a time


@dataclass
class Meeting:
    """One meeting: header info plus its spoken lines."""
    meeting_id: str
    date: date
    department: str
    candidate: str | None                 # None when the transcript says "none"
    panel: dict[str, str] = field(default_factory=dict)   # {"Speaker1": "Person_001"}
    utterances: list[Utterance] = field(default_factory=list)