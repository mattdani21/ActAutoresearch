"""
simulate.py -- generate a real run.

Every experiment here is a genuine ASISA EAC evaluation of a genuine charge
structure through the real gates in prepare.py. Nothing is faked: the staircase
in the UI is the actual ratchet, and the discarded points are structures that
actually failed.

    python simulate.py --n 80 --seed 7

Writes experiments.jsonl, which serve.py reads and the dashboard renders.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scipy.optimize import brentq

from prepare import (
    BASELINE, COMPONENTS, POLICY, PRESCRIBED_GROWTH, ChargeStructure,
    eac_table, evaluate, project,
)

HERE = Path(__file__).parent
LOG = HERE / "experiments.jsonl"
QUEUE = HERE / "review_queue.jsonl"


def pv(cs: ChargeStructure) -> float:
    return project(POLICY, cs, float(POLICY.term_years),
                   PRESCRIBED_GROWTH).provider_charge_pv


BASE_PV = pv(BASELINE)


def rebalance(cs: ChargeStructure, knob: str) -> ChargeStructure:
    """Solve one parameter so the provider's charge PV returns to baseline.
    This is what makes a move revenue-neutral and therefore like-for-like."""
    def f(x: float) -> float:
        return pv(replace(cs, **{knob: x})) - BASE_PV
    lo, hi = 0.0, 0.20 if knob != "admin_fixed_monthly" else 400.0
    try:
        return replace(cs, **{knob: brentq(f, lo, hi, xtol=1e-10)})
    except ValueError:
        return cs


# ---------------------------------------------------------------------------
# The move set. Each returns (structure, label, knob_to_rebalance_or_None).
# ---------------------------------------------------------------------------

def m_advice_to_ongoing(cs, rng):
    if cs.initial_advice_pct <= 1e-9:
        return None
    frac = rng.choice([0.25, 0.5, 0.75, 1.0])
    new_up = cs.initial_advice_pct * (1 - frac)
    out = replace(cs, initial_advice_pct=new_up,
                  initial_advice_months=0 if new_up == 0 else cs.initial_advice_months)
    return out, f"advice upfront {cs.initial_advice_pct*100:.2f}%->{new_up*100:.2f}% of premium", "ongoing_advice_pct"


def m_spread_advice(cs, rng):
    if cs.initial_advice_pct <= 1e-9:
        return None
    months = rng.choice([24, 36, 60])
    if months <= cs.initial_advice_months:
        return None
    scaled = cs.initial_advice_pct * cs.initial_advice_months / months
    out = replace(cs, initial_advice_months=months, initial_advice_pct=scaled)
    return out, f"spread advice over {cs.initial_advice_months}->{months} months", "ongoing_advice_pct"


def m_rand_fee_to_pct(cs, rng):
    if cs.admin_fixed_monthly <= 1e-9:
        return None
    frac = rng.choice([0.3, 0.6, 1.0])
    new_fee = cs.admin_fixed_monthly * (1 - frac)
    out = replace(cs, admin_fixed_monthly=new_fee)
    return out, f"admin rand fee R{cs.admin_fixed_monthly:.0f}->R{new_fee:.0f}/m", "admin_fund_pct"


def m_pct_to_rand_fee(cs, rng):
    if cs.admin_fund_pct <= 0.0005:
        return None
    frac = rng.choice([0.2, 0.4])
    new_pct = cs.admin_fund_pct * (1 - frac)
    out = replace(cs, admin_fund_pct=new_pct)
    return out, f"admin fund charge {cs.admin_fund_pct*100:.2f}%->{new_pct*100:.2f}%", "admin_fixed_monthly"


def m_admin_to_premium(cs, rng):
    if cs.admin_fund_pct <= 0.0005:
        return None
    frac = rng.choice([0.2, 0.4, 0.6])
    new_pct = cs.admin_fund_pct * (1 - frac)
    out = replace(cs, admin_fund_pct=new_pct)
    return out, f"admin fund->premium basis, fund {cs.admin_fund_pct*100:.2f}%->{new_pct*100:.2f}%", "admin_premium_pct"


def m_anniversary_bonus(cs, rng):
    pct = rng.choice([0.01, 0.02, 0.03])
    yrs = tuple(float(p) for p in POLICY.disclosure_periods())
    out = replace(cs, loyalty_bonus_pct=pct, loyalty_bonus_years=yrs)
    return out, f"{pct*100:.0f}% bonus at the 4 disclosure points", "admin_fund_pct"


def m_late_bonus(cs, rng):
    pct = rng.choice([0.02, 0.04])
    out = replace(cs, loyalty_bonus_pct=pct, loyalty_bonus_years=(float(POLICY.term_years),))
    return out, f"{pct*100:.0f}% vesting bonus at term only", "admin_fund_pct"


def m_termination_charge(cs, rng):
    pct = rng.choice([0.02, 0.05])
    yrs = rng.choice([3.0, 5.0])
    out = replace(cs, termination_pct=pct, termination_taper_years=yrs)
    return out, f"{pct*100:.0f}% exit charge tapering to {yrs:.0f}y", "admin_fund_pct"


def m_fold_into_ter(cs, rng):
    if cs.admin_fund_pct <= 0.0005:
        return None
    out = replace(cs, ter=cs.ter + cs.admin_fund_pct, admin_fund_pct=0.0)
    return out, f"fold {cs.admin_fund_pct*100:.2f}% admin into the TER", None


def m_external_rebate(cs, rng):
    pct = rng.choice([0.002, 0.0035])
    out = replace(cs, admin_fixed_monthly=0.0, external_benefit_pct=pct)
    return out, f"rand fee waived via loyalty programme ({pct*100:.2f}%)", None


def m_trim_ongoing(cs, rng):
    d = rng.choice([0.0005, 0.001])
    out = replace(cs, ongoing_advice_pct=max(0.0, cs.ongoing_advice_pct - d))
    return out, f"ongoing advice -{d*100:.2f}% (no offset)", None


MOVES = [
    (m_advice_to_ongoing, 5), (m_spread_advice, 4), (m_rand_fee_to_pct, 4),
    (m_pct_to_rand_fee, 3), (m_admin_to_premium, 4), (m_anniversary_bonus, 3),
    (m_late_bonus, 2), (m_termination_charge, 2), (m_fold_into_ter, 2),
    (m_external_rebate, 2), (m_trim_ongoing, 2),
]
POOL = [m for m, w in MOVES for _ in range(w)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    best = BASELINE
    base_ev = evaluate(POLICY, BASELINE, BASELINE)
    best_metric = base_ev.metric
    t0 = datetime.now(timezone.utc) - timedelta(minutes=6 * args.n)

    records = [{
        "n": 0, "ts": t0.isoformat(timespec="seconds"), "label": "baseline",
        "metric": round(best_metric, 6), "best": round(best_metric, 6),
        "kept": True, "acceptable": True, "failed_gates": [],
        "action": "BASELINE", "verdict": "starting point", "structure": "baseline-RA",
    }]

    n = 0
    while n < args.n:
        move = rng.choice(POOL)
        got = move(best, rng)
        if got is None:
            continue
        cand, label, knob = got
        if knob:
            cand = rebalance(cand, knob)
        cand = replace(cand, name=f"exp-{n+1:03d}", notes=label)

        ev = evaluate(POLICY, best, cand)   # judged against the incumbent
        improved = ev.metric < best_metric - 1e-9
        keep = improved and ev.accepted
        n += 1

        records.append({
            "n": n,
            "ts": (t0 + timedelta(minutes=6 * n)).isoformat(timespec="seconds"),
            "label": label,
            "metric": round(ev.metric, 6),
            "best": round(min(best_metric, ev.metric) if keep else best_metric, 6),
            "kept": keep,
            "acceptable": ev.accepted,
            "failed_gates": [{"gate": g.gate, "clause": g.clause, "detail": g.detail}
                             for g in ev.failed_gates],
            "action": "COMMIT" if keep else "REVERT",
            "verdict": ev.verdict,
            "structure": cand.name,
            "table": {str(p): {k: round(v, 6) for k, v in ev.table[p].items()}
                      for p in POLICY.disclosure_periods()},
        })

        if keep:
            best, best_metric = cand, ev.metric
            print(f"  [{n:3d}] KEEP  {ev.metric*100:6.3f}%  {label}")
        else:
            why = ev.failed_gates[0].clause if ev.failed_gates else "no gain"
            print(f"  [{n:3d}] drop  {ev.metric*100:6.3f}%  {label}  ({why})")

    LOG.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    kept = sum(1 for r in records if r["kept"]) - 1
    print(f"\n{args.n} experiments, {kept} kept improvements")
    print(f"baseline {base_ev.metric*100:.3f}%  ->  best {best_metric*100:.3f}%")
    print(f"written to {LOG.name}")

    # --- the review queue: what a human is asked to sign off on ---------------
    committed = [r for r in records if r["kept"] and r["n"] > 0]
    notable = [r for r in records
               if not r["acceptable"] and r["metric"] < base_ev.metric][:2]
    queue = []
    for r in committed[-2:]:
        queue.append({
            "id": f"ACT-{100 + r['n']}", "track": "Quotations", "area": "EACs",
            "mode": "current method", "title": r["label"],
            "delta_pp": round((r["metric"] - base_ev.metric) * 100, 3),
            "metric": r["metric"], "gates_passed": 4, "gates_total": 4,
            "status": "ready", "experiment": r["n"],
        })
    for r in notable:
        queue.append({
            "id": f"ACT-{100 + r['n']}", "track": "Quotations", "area": "EACs",
            "mode": "experimental", "title": r["label"],
            "delta_pp": round((r["metric"] - base_ev.metric) * 100, 3),
            "metric": r["metric"],
            "gates_passed": 4 - len(r["failed_gates"]), "gates_total": 4,
            "status": "blocked",
            "blocked_by": r["failed_gates"][0] if r["failed_gates"] else None,
            "experiment": r["n"],
        })
    QUEUE.write_text("\n".join(json.dumps(q) for q in queue) + "\n")
    print(f"{len(queue)} items queued for review -> {QUEUE.name}")


if __name__ == "__main__":
    main()
