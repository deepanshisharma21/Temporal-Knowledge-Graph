"""Simple terminal demo of the question functions (no AI assistant needed)."""
from . import queries


def _ask(prompt: str, default: str | None = None):
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def search():
    from .embeddings import search_topics
    question = _ask("Your question", "Who struggled to explain things clearly?")
    department = _ask("Department (Enter for all)")
    for h in search_topics(question, department=department):
        print(f"  {h['score']:.2f} {h['date']} {h['meeting_id']} "
              f"{h['person_id']}: {h['text']}")


def journey():
    candidate = _ask("Candidate ID", "Candidate_01")
    rows = queries.get_candidate_journey(candidate)
    if not rows:
        print("  Nothing found for that candidate.")
        return
    for r in rows:
        print(f"  {r['date']} {r['meeting_id']} ({r['department']}) "
              f"panel={r['panel']} status={r['status']}")


def compare():
    first = _ask("First meeting", "HR_Round1")
    second = _ask("Second meeting", "HR_Round2")
    c = queries.compare_meetings(first, second)
    if c is None:
        print("  One of those meetings was not found.")
        return
    print(f"  {c['earlier']['meeting_id']} ({c['earlier']['date']}) -> "
          f"{c['later']['meeting_id']} ({c['later']['date']}), "
          f"same series: {c['same_series']}")
    for key, value in c["changes"].items():
        print(f"  {key}: {value}")


def concerns():
    topic = _ask("Topic", "communication skills")
    start = _ask("From date YYYY-MM-DD (Enter to skip)")
    end = _ask("To date YYYY-MM-DD (Enter to skip)")
    f = queries.find_cross_group_concerns(topic, start, end)
    print("  departments:", f["groups"])
    for r in f["raised"]:
        print(f"  {r['date']} {r['group']} {r['person_id']} "
              f"({r['meeting_id']}): {r['quote']}")


def person():
    person_id = _ask("Person ID", "Person_001")
    t = queries.get_person_timeline(person_id)
    if not t["said"]:
        print("  Nothing found for that person.")
        return
    for r in t["said"]:
        print(f"  {r['date']} {r['meeting_id']}: {r['text']}")
    for r in t["concerns"]:
        print(f"  concern raised: {r['topic']} ({r['date']} {r['meeting_id']})")


def meeting():
    meeting_id = _ask("Meeting", "HR_Round2")
    m = queries.get_meeting(meeting_id)
    if m is None:
        print("  Meeting not found.")
        return
    print(f"  {m['date']} {m['department']} candidate={m['candidate']} "
          f"attendees={m['attendees']}")
    for r in m["lines"]:
        print(f"  #{r['idx']} {r['person_id']}: {r['text']}")


MENU = {
    "1": ("Search by meaning", search),
    "2": ("A candidate's journey across rounds", journey),
    "3": ("What changed between two meetings", compare),
    "4": ("Concerns raised across departments", concerns),
    "5": ("Everything one person said", person),
    "6": ("Read one meeting", meeting),
}


def main():
    while True:
        print("\nTemporal Knowledge Graph - ask a question")
        for key, (label, _) in MENU.items():
            print(f"  {key}. {label}")
        print("  0. Quit")
        choice = input("Choose: ").strip()
        if choice == "0":
            break
        if choice not in MENU:
            print("Please choose a number from the list.")
            continue
        try:
            MENU[choice][1]()
        except Exception as error:
            print(f"  Something went wrong: {error}")
            print("  (Is Neo4j running?)")


if __name__ == "__main__":
    main()