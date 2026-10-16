"""Extraction: topics, concerns and status from a spoken line (HLD Section 3).

This is the free keyword version. It returns the SAME format a Claude-based
extractor would, so the two can be swapped later without touching the rest.
"""
import re
from typing import Literal

from pydantic import BaseModel

from .models import Meeting

TOPIC_KEYWORDS = {
    "communication": "communication skills",
    "technical": "technical skills",
    "system design": "system design",
}
CONCERN_CUES = [r"\bstruggl", r"\bunclear\b", r"\bconcern", r"\bweak\b", r"\bpoor\b"]
STATUS_PATTERNS = [
    (r"\bon hold\b", "on hold"),
    (r"\bmove forward\b", "move forward"),
]


class Extraction(BaseModel):
    """The fixed output format. Anything that doesn't fit is rejected."""
    topics: list[str] = []
    concerns: list[str] = []      # topics that were mentioned as a problem
    status: Literal["on hold", "move forward"] | None = None


def extract_utterance(text: str) -> Extraction:
    topics: list[str] = []
    concerns: list[str] = []
    status = None

    for sentence in re.split(r"(?<=[.!?])\s+", text):
        s = sentence.lower()
        has_concern = any(re.search(cue, s) for cue in CONCERN_CUES)

        for keyword, label in TOPIC_KEYWORDS.items():
            if keyword in s:
                if label not in topics:
                    topics.append(label)
                if has_concern and label not in concerns:
                    concerns.append(label)

        if status is None:
            for pattern, label in STATUS_PATTERNS:
                if re.search(pattern, s):
                    status = label
                    break

    return Extraction(topics=topics, concerns=concerns, status=status)


def extract_all(meetings: list[Meeting]) -> dict[str, Extraction]:
    """Returns {utterance uid: Extraction}, e.g. 'HR_Round1#2'."""
    results = {}
    for meeting in meetings:
        for utt in meeting.utterances:
            results[f"{utt.meeting_id}#{utt.index}"] = extract_utterance(utt.text)
    return results


if __name__ == "__main__":
    from .parser import load_transcripts

    meetings = load_transcripts()
    results = extract_all(meetings)
    for m in meetings:
        for u in m.utterances:
            ex = results[f"{m.meeting_id}#{u.index}"]
            if ex.topics or ex.concerns or ex.status:
                print(f"{m.meeting_id} #{u.index} | topics={ex.topics} "
                      f"| concerns={ex.concerns} | status={ex.status}")
    print(f"\nExtracted from {len(results)} lines")