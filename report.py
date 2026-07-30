"""
report.py -- the handoff.

Produces the one-page spike report that lands with the basis writer for a
go/no-go before it reaches the lead actuary. Everything in it is reproducible
from the repo: the code, the log, the commit.

    python report.py > report.md
"""

from __future__ import annotations

import json
from pathlib import Path

from prepare import (
    BASELINE, COMPONENTS, POLICY, PRESCRIBED_GROWTH, RA_LAST_DISCLOSURE_AGE,
    eac_table, evaluate, project,
)
import candidates

def rejections(log, limit: int = 6) -> str:
    """The rejections a reviewer should actually read: cheapest-scoring failures
    first, deduplicated by clause so one pattern does not fill the page."""
    rows = [r for r in log if r.get("action") == "REVERT" and r.get("failed_gates")]
    rows.sort(key=lambda r: r["metric"])
    seen, labels, out = {}, set(), []
    for r in rows:
        clause = r["failed_gates"][0]["clause"]
        seen[clause] = seen.get(clause, 0) + 1
        label = r.get("label") or r.get("structure") or r.get("name", "?")
        if label in labels or seen[clause] > 3 or len(out) >= limit:
            continue
        labels.add(label)
        out.append(f"- **{label}** — metric {r['metric']*100:.3f}%, "
                   f"failed clause {clause}")
    tally = ", ".join(f"{c}: {n}" for c, n in sorted(seen.items(), key=lambda x: -x[1]))
    return ("\n".join(out) or "- none") + f"\n\nAll failures by clause — {tally}."


LABELS = {"imc": "Investment management", "advice": "Advice",
          "admin": "Administration", "other": "Other"}


def md_table(cs) -> str:
    tbl = eac_table(POLICY, cs)
    ps = POLICY.disclosure_periods()
    head = "| Impact of charges | " + " | ".join(f"{p} yr" for p in ps) + " |"
    sep = "|---|" + "|".join("---:" for _ in ps) + "|"
    rows = [f"| {LABELS[c]} | " + " | ".join(f"{tbl[p][c]*100:.2f}%" for p in ps) + " |"
            for c in COMPONENTS]
    total = "| **Effective Annual Cost** | " + " | ".join(
        f"**{tbl[p]['total']*100:.2f}%**" for p in ps) + " |"
    return "\n".join([head, sep, *rows, total])


def main() -> None:
    winner = candidates.LEVEL_ADVICE
    ev = evaluate(POLICY, BASELINE, winner)
    base_ev = evaluate(POLICY, BASELINE, BASELINE)
    t = float(POLICY.term_years)
    base_pv = project(POLICY, BASELINE, t, PRESCRIBED_GROWTH).provider_charge_pv
    cand_pv = project(POLICY, winner, t, PRESCRIBED_GROWTH).provider_charge_pv

    log = []
    p = Path(__file__).parent / "experiments.jsonl"
    if p.exists():
        log = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

    print(f"""# Spike report: levelling the upfront advice charge on a recurring-premium RA

**For:** basis writer, go/no-go before lead actuary
**Status:** committed to main — 1 of {len(log)} candidates this run
**Reproduce:** `git checkout {winner.name} && python run.py`

## Verdict

**Worth a product actuary's time.** Not a recommendation to change a product.

## The claim, stated falsifiably

Removing the year-1 upfront advice charge and recovering the identical present
value as a level ongoing charge lowers the disclosed EAC at every disclosure
period short of the full term, without reducing the provider's charge income,
and the saving is not an artefact of where the Standard takes its measurements.

## Method

ASISA Retail Standard on EAC (22 May 2020), RIY methodology per para 6.3, at
the prescribed {PRESCRIBED_GROWTH*100:.0f}% growth (para 6.3 step 3). Simplified methodology applied
where para 4.7 conditions are met; single RIY calculation per component
otherwise (para 4.9); last component derived as the balancing item (para 6.4).

Disclosure periods 1, 3, 5 years and term to age {RA_LAST_DISCLOSURE_AGE} (para 4.3).

**Policy:** entry age {POLICY.entry_age}, R{POLICY.monthly_premium:,.0f}/month escalating at
{POLICY.premium_escalation*100:.0f}% p.a., {POLICY.term_years}-year term. **Synthetic.**

## Result

**Baseline**

{md_table(BASELINE)}

**Candidate**

{md_table(winner)}

Mean disclosed EAC {base_ev.metric*100:.3f}% → {ev.metric*100:.3f}% ({(ev.metric-base_ev.metric)*100:+.3f}pp).
Year-1 EAC {eac_table(POLICY,BASELINE)[1]['total']*100:.2f}% → {eac_table(POLICY,winner)[1]['total']*100:.2f}%.

Provider charge PV R{base_pv:,.0f} → R{cand_pv:,.0f} ({(cand_pv/base_pv-1)*100:+.2f}%).

## Acceptability

{chr(10).join(f"- **{g.gate}** (clause {g.clause}) — {'PASS' if g.passed else 'FAIL'}. {g.detail}" for g in ev.gates)}

## What this does NOT show

- The charge levels are synthetic and are not Sanlam's. Nothing here is a
  statement about an actual product.
- Revenue neutrality is measured as PV of charges at the prescribed 6%, not
  against a profit model. New business strain, commission regulation under the
  FAIS/FSCA commission framework, and adviser behaviour are all out of scope
  and all of them may dominate.
- Persistency is not modelled. The claim that most investors do not hold an RA
  to age 55 is asserted, not evidenced. **This is the first thing to check.**
- No allowance for the practical question of whether advisers would write the
  business at a level fee.

## Cost to take further

Roughly 3 person-days to rerun against a real product's charge basis and a real
persistency table, plus access to the RA experience data.

## Rejected this run

{rejections(log)}

The rejections under clause 3.1.6.2 are the ones worth reading. Several scored
better on the metric than the candidate above and were reverted anyway, because
the saving existed only where the Standard takes its measurements.
""")


if __name__ == "__main__":
    main()
