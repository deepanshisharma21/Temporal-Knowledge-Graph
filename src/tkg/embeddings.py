"""Search by meaning (HLD Section 3 'searchable by meaning', Section 10 search_topics)."""
import numpy as np

from .queries import _d, _query

MODEL_NAME = "all-MiniLM-L6-v2"      # small, free, runs on your laptop
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]):
    return _get_model().encode(texts, normalize_embeddings=True)


def embed_all() -> int:
    """Store a meaning-vector on every Utterance node. Safe to run again."""
    rows = _query("MATCH (u:Utterance) RETURN u.uid AS uid, u.text AS text ORDER BY uid")
    vectors = embed_texts([r["text"] for r in rows])
    payload = [
        {"uid": r["uid"], "embedding": [float(x) for x in v]}
        for r, v in zip(rows, vectors)
    ]
    _query(
        "UNWIND $rows AS row "
        "MATCH (u:Utterance {uid: row.uid}) SET u.embedding = row.embedding",
        rows=payload,
    )
    return len(payload)


def search_topics(question: str, department: str | None = None,
                  start: str | None = None, end: str | None = None,
                  top_k: int = 3) -> list[dict]:
    """Lines closest in meaning to the question, with meeting, date, speaker."""
    rows = _query(
        "MATCH (m:Meeting)-[:HAS_UTTERANCE]->(u:Utterance) "
        "WHERE u.embedding IS NOT NULL "
        "  AND ($dept IS NULL OR m.department = $dept) "
        "  AND ($start IS NULL OR m.date >= date($start)) "
        "  AND ($end IS NULL OR m.date <= date($end)) "
        "OPTIONAL MATCH (p:Person)-[:SAID]->(u) "
        "OPTIONAL MATCH (u)-[:ABOUT]->(t:Topic) "
        "RETURN u.uid AS uid, u.text AS text, u.embedding AS embedding, "
        "       m.meeting_id AS meeting_id, m.date AS date, "
        "       p.person_id AS person_id, collect(DISTINCT t.label) AS topics",
        dept=department, start=start, end=end,
    )
    if not rows:
        return []
    question_vector = embed_texts([question])[0]
    matrix = np.array([r["embedding"] for r in rows])
    scores = matrix @ question_vector          # cosine similarity (vectors are normalised)
    best = np.argsort(-scores)[:top_k]
    return [
        {
            "score": round(float(scores[i]), 2),
            "meeting_id": rows[i]["meeting_id"],
            "date": _d(rows[i]["date"]),
            "person_id": rows[i]["person_id"],
            "text": rows[i]["text"],
            "topics": rows[i]["topics"],
        }
        for i in best
    ]


if __name__ == "__main__":
    print("Embedded", embed_all(), "lines\n")
    tests = [
        ("Who struggled to explain things clearly?", None),
        ("Was there a worry about system design?", None),
        ("Should the candidate go ahead?", None),
        ("problems with how new people talk to the team", "Engineering"),
    ]
    for question, dept in tests:
        label = f"  [department={dept}]" if dept else ""
        print(f"Q: {question}{label}")
        for h in search_topics(question, department=dept):
            print(f"  {h['score']:.2f} {h['date']} {h['meeting_id']} "
                  f"{h['person_id']}: {h['text']}")
        print()