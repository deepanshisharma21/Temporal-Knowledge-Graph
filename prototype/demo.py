"""
Temporal Knowledge Graph over Meeting Transcripts - SIMPLE DEMO (prototype)
Run:  python demo.py
"""
import re
import networkx as nx

# ---------------------------------------------------------------
# 1. SAMPLE TRANSCRIPTS (made-up, anonymised: roles only, no names)
# ---------------------------------------------------------------
TRANSCRIPTS = [
    """MEETING: HR_Round1
DATE: 2026-09-01
DEPARTMENT: HR
CANDIDATE: Candidate_01
PANEL: Speaker1=Person_001, Speaker2=Person_002
---
Speaker1: Tell us about your last project.
Speaker2: I noticed the candidate struggled with communication when explaining the design.
Speaker1: Agreed, communication was unclear. Technical skills look good though.
Speaker2: Overall I am unsure, let us put the candidate on hold for now.""",

    """MEETING: HR_Round2
DATE: 2026-09-08
DEPARTMENT: HR
CANDIDATE: Candidate_01
PANEL: Speaker1=Person_001, Speaker2=Person_003
---
Speaker1: Communication was much clearer this time.
Speaker2: I have a concern about system design depth, it was weak.
Speaker1: Fair point. Still, I recommend we move forward with the candidate.""",

    """MEETING: Eng_Sync1
DATE: 2026-09-10
DEPARTMENT: Engineering
CANDIDATE: none
PANEL: Speaker1=Person_004, Speaker2=Person_005
---
Speaker1: New hires seem to have poor communication with the team.
Speaker2: Yes, communication is a recurring concern for us too.""",
]

# ---------------------------------------------------------------
# 2. "EXTRACTION" (simple keyword rules; real version = Claude API)
# ---------------------------------------------------------------
TOPICS = {
    "communication": ["communication"],
    "system design": ["system design"],
    "technical skills": ["technical skills"],
}
# (phrase, status)  - first match wins
STATUS_RULES = [("move forward", "Advance"), ("on hold", "On Hold"), ("reject", "Rejected")]


def parse(text):
    header, body = text.split("---")
    meta = dict(line.split(": ", 1) for line in header.strip().splitlines())
    panel = dict(p.split("=") for p in meta["PANEL"].split(", "))
    lines = []
    for line in body.strip().splitlines():
        speaker, said = line.split(": ", 1)
        lines.append((panel[speaker], said))   # (Person_ID, text)
    return meta, lines


# ---------------------------------------------------------------
# 3. BUILD THE GRAPH (networkx = in-memory graph; Neo4j later)
# ---------------------------------------------------------------
G = nx.MultiDiGraph()


def build_graph():
    previous_meeting = {}   # candidate -> last meeting (to link "comes after")
    current_status = {}     # candidate -> current status node id
    for text in TRANSCRIPTS:
        meta, lines = parse(text)
        m, date = meta["MEETING"], meta["DATE"]
        G.add_node(m, kind="Meeting", date=date, dept=meta["DEPARTMENT"])
        cand = meta["CANDIDATE"]
        if cand != "none":
            G.add_node(cand, kind="Candidate")
            G.add_edge(m, cand, rel="IS_ABOUT")
            if cand in previous_meeting:   # time order between rounds
                G.add_edge(m, previous_meeting[cand], rel="COMES_AFTER")
            previous_meeting[cand] = m

        for person, said in lines:
            G.add_node(person, kind="Person")
            G.add_edge(person, m, rel="TOOK_PART_IN", date=date)
            low = said.lower()
            for topic, words in TOPICS.items():
                if any(w in low for w in words):
                    G.add_node(topic, kind="Topic")
                    G.add_edge(person, topic, rel="RAISED", date=date, meeting=m, text=said)
            # status changes: keep the OLD one, close its time window
            if cand != "none":
                for phrase, status in STATUS_RULES:
                    if phrase in low:
                        sid = f"{cand}:{status}:{date}"
                        G.add_node(sid, kind="Status", value=status, valid_from=date, valid_to=None)
                        G.add_edge(cand, sid, rel="HAS_STATUS")
                        if cand in current_status:
                            old = current_status[cand]
                            G.nodes[old]["valid_to"] = date          # not deleted, just ended
                            G.add_edge(sid, old, rel="REPLACES")
                        current_status[cand] = sid
                        break


# ---------------------------------------------------------------
# 4. QUERY FUNCTIONS (same ideas as the HLD "AI assistant" functions)
# ---------------------------------------------------------------
def get_candidate_journey(cand):
    print(f"\n=== Journey of {cand} ===")
    meetings = [u for u, v, d in G.in_edges(cand, data=True) if d["rel"] == "IS_ABOUT"]
    for m in sorted(meetings, key=lambda x: G.nodes[x]["date"]):
        panel = sorted({u for u, v, d in G.in_edges(m, data=True) if d["rel"] == "TOOK_PART_IN"})
        print(f"{G.nodes[m]['date']}  {m}  panel: {', '.join(panel)}")
    for _, s, d in G.out_edges(cand, data=True):
        if d["rel"] == "HAS_STATUS":
            n = G.nodes[s]
            print(f"  status: {n['value']}  (from {n['valid_from']} to {n['valid_to'] or 'now'})")


def concerns_in(meeting):
    out = set()
    for p, t, d in G.edges(data=True):
        if d["rel"] == "RAISED" and d["meeting"] == meeting:
            out.add(t)
    return out


def compare_meetings(m1, m2):
    a, b = concerns_in(m1), concerns_in(m2)
    print(f"\n=== What changed: {m1} -> {m2} ===")
    print("New topics raised  :", sorted(b - a) or "none")
    print("No longer raised   :", sorted(a - b) or "none")
    print("Raised in both     :", sorted(a & b) or "none")


def find_cross_group_concerns(topic):
    print(f"\n=== Who raised '{topic}' across departments ===")
    for p, t, d in G.edges(data=True):
        if d["rel"] == "RAISED" and t == topic:
            dept = G.nodes[d["meeting"]]["dept"]
            print(f"{d['date']}  {p} ({dept}, {d['meeting']}): \"{d['text']}\"")


# ---------------------------------------------------------------
if __name__ == "__main__":
    build_graph()
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    get_candidate_journey("Candidate_01")
    compare_meetings("HR_Round1", "HR_Round2")
    find_cross_group_concerns("communication")