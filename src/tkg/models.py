"""Data models for the Temporal Knowledge Graph (follows HLD Section 5)."""
import datetime as dt
from dataclasses import dataclass, field


# ---------- Things we store (HLD 5.1) ----------

@dataclass
class Group:
    """A department, e.g. HR or Engineering."""
    name: str


@dataclass
class Person:
    """A stable made-up ID that follows one person across meetings."""
    person_id: str                     # e.g. "Person_017"
    group: str | None = None           # department name
    role: str | None = None
    confidence: float = 1.0            # how sure we are this is really them


@dataclass
class Candidate:
    candidate_id: str                  # e.g. "Candidate_01"


@dataclass
class MeetingSeries:
    """Meetings that belong together, e.g. the HR interview rounds."""
    name: str
    frequency: str | None = None


@dataclass
class Topic:
    """Short label such as 'communication skills'."""
    label: str


@dataclass
class Utterance:
    """What was said: one spoken line."""
    meeting_id: str
    index: int                         # position in the meeting (0, 1, 2...)
    speaker_label: str                 # "Speaker1" - restarts every meeting
    text: str
    date: dt.date
    timestamp: dt.time | None = None   # time of day, if the transcript has it
    person_id: str | None = None       # filled in LATER by speaker matching
    embedding: list[float] | None = None   # for search by meaning


@dataclass
class Meeting:
    meeting_id: str
    date: dt.date
    department: str
    start_time: dt.time | None = None
    series: str | None = None          # name of the MeetingSeries
    candidate_id: str | None = None    # None when the transcript says "none"
    panel: dict[str, str] = field(default_factory=dict)  # {"Speaker1": "Person_001"}
    utterances: list[Utterance] = field(default_factory=list)


# ---------- Things that change over time (HLD Section 7) ----------

@dataclass
class StatusFact:
    """A status that was true for a window of time, e.g. 'on hold'.
    Old facts are never deleted: valid_to is filled in and the new fact
    points back to the one it replaces."""
    subject_id: str                    # a candidate or project ID
    status: str                        # e.g. "on hold", "move forward"
    valid_from: dt.date
    valid_to: dt.date | None = None    # None = still true today
    source_meeting_id: str | None = None
    replaces: str | None = None        # id of the older StatusFact