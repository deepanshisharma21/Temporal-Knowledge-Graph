"""MCP server: the fixed list of questions an AI assistant may ask (HLD Section 10).

IMPORTANT: never use print() in this file. The server talks to the assistant
through standard output, so a stray print would break the connection.
"""
from mcp.server.fastmcp import FastMCP

from . import queries
from .embeddings import search_topics as _search_topics
from .identity import assign_people  # noqa: F401  (kept for later speaker matching)

mcp = FastMCP("temporal-knowledge-graph")


@mcp.tool()
def search_topics(question: str, department: str | None = None,
                  start: str | None = None, end: str | None = None) -> list[dict]:
    """Find the spoken lines closest in meaning to a question. Starting point for
    most questions. Optional department and dates (YYYY-MM-DD)."""
    return _search_topics(question, department=department, start=start, end=end)


@mcp.tool()
def get_person_timeline(person_id: str) -> dict:
    """Everything one person said and every concern they raised, in date order,
    across all their meetings (e.g. person_id 'Person_001')."""
    return queries.get_person_timeline(person_id)


@mcp.tool()
def get_candidate_journey(candidate_id: str) -> list[dict]:
    """Every interview round for a candidate, in order, with the panel and the
    candidate's status at that point (e.g. 'Candidate_01')."""
    return queries.get_candidate_journey(candidate_id)


@mcp.tool()
def compare_meetings(meeting_a: str, meeting_b: str) -> dict | None:
    """What changed between two meetings: status, new topics, new concerns."""
    return queries.compare_meetings(meeting_a, meeting_b)


@mcp.tool()
def get_meeting(meeting_id: str) -> dict | None:
    """Everything about one meeting: who was there and what was said."""
    return queries.get_meeting(meeting_id)


@mcp.tool()
def find_cross_group_concerns(topic: str, start: str | None = None,
                              end: str | None = None) -> dict:
    """Who raised a concern about a topic (e.g. 'communication skills'),
    in which department, when and in which meeting. Optional dates (YYYY-MM-DD)."""
    return queries.find_cross_group_concerns(topic, start, end)


@mcp.tool()
def get_group_activity(group: str, start: str | None = None,
                       end: str | None = None) -> list[dict]:
    """The meetings a department (e.g. 'HR') had in a date range (YYYY-MM-DD)."""
    return queries.get_group_activity(group, start, end)


@mcp.tool()
def resolve_speaker(meeting_id: str, speaker_label: str) -> dict:
    """Which stable person a speaker label (e.g. 'Speaker2') maps to in a meeting,
    or that it needs a human check."""
    return queries.resolve_speaker(meeting_id, speaker_label)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()