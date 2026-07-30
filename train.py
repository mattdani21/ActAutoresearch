"""
train.py -- the ONE file the agent edits.

Propose a charge structure for the RA in prepare.py. Everything here is fair
game: the level of each charge, how it is expressed (% of premium, % of fund,
rand amount), when it is taken, and what structural features exist (tapers,
bonuses, tiering).

You are optimising `metric` = the mean of the four EAC values that would be
DISCLOSED under the ASISA Standard (1, 3, 5 years and term to age 55). Lower
is better.

You may not edit prepare.py. It defines the measure and the acceptability
gates. If a change only improves the metric by moving where the measurement
falls, the gates will catch it and the run will be reverted.
"""

from prepare import (
    BASELINE, POLICY, ChargeStructure, evaluate, format_evaluation,
)

# ---------------------------------------------------------------------------
# CURRENT PROPOSAL -- edit this
# ---------------------------------------------------------------------------

CANDIDATE = ChargeStructure(
    name="level-advice",

    # investment management -- unchanged
    ter=0.0095,
    transaction_costs=0.0015,

    # advice: the upfront charge is removed entirely and recovered as a level
    # ongoing charge calibrated to leave the provider's charge PV unchanged.
    initial_advice_pct=0.0000,
    initial_advice_months=0,
    ongoing_advice_pct=0.005142,

    # administration -- unchanged
    admin_fund_pct=0.0050,
    admin_fixed_monthly=35.0,

    notes=("Replaces the year-1 upfront advice charge with a level ongoing "
           "charge at equal provider charge PV. Hypothesis: most of the "
           "year-1 EAC is the upfront charge amortised over a single year, "
           "and levelling it is a real saving for anyone who does not hold "
           "to age 55 -- which is most people."),
)


if __name__ == "__main__":
    ev = evaluate(POLICY, BASELINE, CANDIDATE)
    print(format_evaluation(POLICY, BASELINE, CANDIDATE, ev))
