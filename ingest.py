"""
ingest.py -- the research lane.

Pulls real papers from the arXiv API and ranks them against the department's
stated problem surface. This is the only part of the pitch that touches the
outside world, and it is deliberately real: the charge data is synthetic, the
literature is not.

Needs network access to export.arxiv.org. Run it a few days before the pitch so
you have a genuine backlog to show, not an empty queue.

    python ingest.py --days 7
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ATOM = "{http://www.w3.org/2005/Atom}"
API = "http://export.arxiv.org/api/query?"
QUEUE = Path(__file__).parent / "queue.jsonl"

# Categories where methods that transfer to charge-structure work actually live.
CATEGORIES = ["q-fin.RM", "q-fin.PM", "q-fin.MF", "math.OC", "stat.AP", "stat.ME"]

# The ranking rubric. This is the department's, not the model's -- it should be
# argued about and edited in the room. A visible rubric is an asset; a black-box
# relevance score is a trust problem.
RUBRIC = {
    "constrained optimisation": 3.0,
    "pareto": 2.5,
    "multi-objective": 2.5,
    "sensitivity analysis": 3.0,
    "sobol": 2.5,
    "uncertainty quantification": 2.5,
    "robustness": 2.0,
    "distribution-free": 2.0,
    "fee": 3.0,
    "charge": 2.5,
    "cost disclosure": 3.5,
    "expense ratio": 3.0,
    "retirement": 2.5,
    "annuity": 2.5,
    "pension": 2.5,
    "lapse": 2.5,
    "persistency": 2.5,
    "surrender": 2.0,
    "policyholder": 2.0,
    "internal rate of return": 2.0,
    "path dependen": 1.5,
    "regime": 1.0,
}


def fetch(days: int, per_cat: int = 60) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    for cat in CATEGORIES:
        params = urllib.parse.urlencode({
            "search_query": f"cat:{cat}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": per_cat,
        })
        with urllib.request.urlopen(API + params, timeout=30) as r:
            root = ET.fromstring(r.read())
        for e in root.findall(f"{ATOM}entry"):
            pub = datetime.fromisoformat(
                e.find(f"{ATOM}published").text.replace("Z", "+00:00"))
            if pub < cutoff:
                continue
            out.append({
                "id": e.find(f"{ATOM}id").text,
                "title": " ".join(e.find(f"{ATOM}title").text.split()),
                "abstract": " ".join(e.find(f"{ATOM}summary").text.split()),
                "published": pub.date().isoformat(),
                "category": cat,
            })
    seen, uniq = set(), []
    for p in out:
        if p["id"] not in seen:
            seen.add(p["id"])
            uniq.append(p)
    return uniq


def score(paper: dict) -> tuple[float, list[str]]:
    text = (paper["title"] + " " + paper["abstract"]).lower()
    hits = [(w, wt) for w, wt in RUBRIC.items() if w in text]
    return sum(wt for _, wt in hits), [w for w, _ in hits]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    papers = fetch(args.days)
    ranked = []
    for p in papers:
        s, hits = score(p)
        if s > 0:
            p["score"], p["matched"] = round(s, 2), hits
            ranked.append(p)
    ranked.sort(key=lambda p: -p["score"])

    with QUEUE.open("w") as fh:
        for p in ranked:
            fh.write(json.dumps(p) + "\n")

    print(f"ingested {len(papers)} papers from the last {args.days} days across "
          f"{len(CATEGORIES)} categories")
    print(f"{len(ranked)} scored above zero against the rubric\n")
    for p in ranked[:args.top]:
        print(f"  {p['score']:5.1f}  {p['published']}  {p['title'][:78]}")
        print(f"         matched: {', '.join(p['matched'][:6])}")
    print(f"\nfunnel: {len(papers)} -> {len(ranked)} -> top {args.top} for triage")
    print(f"queue written to {QUEUE.name}")


if __name__ == "__main__":
    main()
