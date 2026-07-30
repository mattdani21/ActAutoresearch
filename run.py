"""
run.py -- the ratchet.

    ARE MY EACs GETTING LOWER?   -> metric improved on best-so-far?
    WHY?                          -> which component moved, and by how much
    IS IT ACCEPTABLE?             -> the four gates in prepare.py
    COMMIT TO MAIN                -> only if both

Anything that fails is reverted and logged. The log of rejections is the
output the reviewer actually reads.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from prepare import (
    BASELINE, COMPONENTS, POLICY, ChargeStructure, eac_table, evaluate,
    format_evaluation,
)

LOG = Path(__file__).parent / "experiments.jsonl"
BEST = Path(__file__).parent / "best.json"


def best_so_far() -> float:
    if BEST.exists():
        return json.loads(BEST.read_text())["metric"]
    return evaluate(POLICY, BASELINE, BASELINE).metric


def why(candidate: ChargeStructure) -> str:
    """The 'WHY?' step -- attribute the movement to components, per period."""
    b, c = eac_table(POLICY, BASELINE), eac_table(POLICY, candidate)
    worst_p = max(POLICY.disclosure_periods(),
                  key=lambda p: b[p]["total"] - c[p]["total"])
    moves = sorted(((c[worst_p][k] - b[worst_p][k], k) for k in COMPONENTS),
                   key=lambda x: x[0])
    d, k = moves[0]
    return (f"largest gain at the {worst_p}y disclosure point "
            f"({(b[worst_p]['total'] - c[worst_p]['total']) * 100:+.2f}pp), "
            f"driven by {k} ({d * 100:+.2f}pp)")


def step(candidate: ChargeStructure, verbose: bool = True) -> dict:
    ev = evaluate(POLICY, BASELINE, candidate)  # single-step demo: baseline is the incumbent
    prev = best_so_far()
    improved = ev.metric < prev - 1e-9
    commit = improved and ev.accepted

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": candidate.name,
        "metric": round(ev.metric, 6),
        "best_so_far": round(prev, 6),
        "lower": improved,
        "why": why(candidate) if improved else "no improvement",
        "acceptable": ev.accepted,
        "failed_gates": [{"gate": g.gate, "clause": g.clause, "detail": g.detail}
                         for g in ev.failed_gates],
        "action": "COMMIT" if commit else "REVERT",
        "verdict": ev.verdict,
    }
    with LOG.open("a") as fh:
        fh.write(json.dumps(record) + "\n")

    if commit:
        BEST.write_text(json.dumps({"name": candidate.name, "metric": ev.metric}, indent=2))

    if verbose:
        print(format_evaluation(POLICY, BASELINE, candidate, ev))
        print(f"ARE MY EACs GETTING LOWER?  {'Y' if improved else 'N'}"
              f"   ({ev.metric * 100:.3f}% vs best {prev * 100:.3f}%)")
        if improved:
            print(f"WHY?                        {record['why']}")
        print(f"IS IT ACCEPTABLE?           {'Y' if ev.accepted else 'N'}")
        for g in ev.failed_gates:
            print(f"                            ^ clause {g.clause}: {g.detail}")
        print(f"ACTION:                     {record['action']}"
              f"{'  ->  git commit -m ' + repr(candidate.name) if commit else '  ->  git checkout train.py'}")
        print()
    return record


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        import candidates
        for cs in candidates.ALL:
            step(cs)
    else:
        from train import CANDIDATE
        step(CANDIDATE)
