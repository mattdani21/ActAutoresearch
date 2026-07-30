"""
candidates.py -- the pre-baked run for the pitch.

Four structures the loop proposed. One is a real saving. Three lower the
disclosed number without lowering what the investor actually pays, and each
trips a different clause of the Standard.

The third one scores BETTER on the metric than the honest one. It is still
rejected. That is the whole argument for the architecture.
"""

from prepare import ChargeStructure

# ---------------------------------------------------------------------------
# 1. ACCEPT -- level the upfront advice charge
# ---------------------------------------------------------------------------
LEVEL_ADVICE = ChargeStructure(
    name="level-advice",
    initial_advice_pct=0.0,
    initial_advice_months=0,
    ongoing_advice_pct=0.005142,          # revenue-neutral to the baseline
    notes=("Removes the year-1 upfront advice charge and recovers it as a level "
           "ongoing charge at identical provider charge PV. The saving is real: "
           "the investor is better off at every holding period short of the full "
           "term, and neutral at the term."),
)

# ---------------------------------------------------------------------------
# 2. REJECT (3.1.6.2) -- anniversary bonus timed to the measurement points
# ---------------------------------------------------------------------------
ANNIVERSARY_BONUS = ChargeStructure(
    name="anniversary-bonus",
    admin_fund_pct=0.009269,              # funds the bonus, revenue-neutral
    loyalty_bonus_pct=0.030,
    loyalty_bonus_years=(1.0, 3.0, 5.0, 20.0),
    notes=("Pays a 3% loyalty bonus on the fund at exactly 1, 3, 5 and 20 years "
           "-- the four mandatory disclosure points -- funded by a higher annual "
           "administration charge. Every disclosed number improves. Anyone who "
           "exits between those points pays the higher charge and receives "
           "nothing."),
)

# ---------------------------------------------------------------------------
# 3. REJECT (3.1.16) -- charge reduction funded outside the product
# ---------------------------------------------------------------------------
EXTERNAL_REBATE = ChargeStructure(
    name="loyalty-programme-rebate",
    admin_fixed_monthly=0.0,
    admin_fund_pct=0.0050,
    external_benefit_pct=0.0035,
    notes=("Drops the monthly rand administration fee for members of the group "
           "loyalty programme, recovered through the programme rather than the "
           "product."),
)

# ---------------------------------------------------------------------------
# 4. REJECT (3.1.12 / 3.1.13) -- undisclosed charge-shifting between components
# ---------------------------------------------------------------------------
COMPONENT_SHIFT = ChargeStructure(
    name="component-shift",
    ter=0.0145,                           # admin fund charge folded into the TER
    transaction_costs=0.0015,
    admin_fund_pct=0.0,
    notes=("Moves the annual administration charge into the underlying fund's "
           "TER. Total cost to the investor is unchanged."),
)

ALL = [LEVEL_ADVICE, ANNIVERSARY_BONUS, EXTERNAL_REBATE, COMPONENT_SHIFT]
