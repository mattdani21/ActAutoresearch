"""
prepare.py -- FIXED. The agent must never modify this file.

Implements the ASISA Retail Standard on Effective Annual Cost (EAC), 22 May 2020,
for a recurring-premium Retirement Annuity, plus the acceptability gates that
decide whether a proposed charge structure may be committed to main.

Clause references in comments are to the Standard.

Design note (this is the whole point of the architecture):
    train.py  -- the agent may rewrite freely. It proposes charge structures.
    prepare.py -- the agent may not touch. It defines the measure and the rules.

An agent that can rewrite its own scoring function is not doing research,
it is doing wishful thinking. The separation is the control.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Callable

from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# Prescribed constants (the Standard, not our choice)
# ---------------------------------------------------------------------------

# para 6.3 Step 3: "investment growth is currently fixed at 6% effective per annum
# (gross of all charges, but net of tax)"
PRESCRIBED_GROWTH = 0.06

# para 4.3: mandatory disclosure periods are 1, 3, 5 years and end of term.
# "In the case of a Retirement Annuity ... which does not have a term, age 55
# should be used as the last disclosure period."
RA_LAST_DISCLOSURE_AGE = 55

VAT = 0.15  # para 4.4: all charge components shown inclusive of VAT

COMPONENTS = ("imc", "advice", "admin", "other")

# para 4.2: EAC[total] = EAC[IMC] + EAC[Advice] + EAC[Admin] + EAC[Other]
# para 6.4: the LAST component is derived as RIY_total minus the others, so the
# four components sum exactly to the total. We treat "other" as the last.
LAST_COMPONENT = "other"


# ---------------------------------------------------------------------------
# The policy: a recurring-premium RA
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Policy:
    entry_age: int = 35
    monthly_premium: float = 2_500.0
    premium_escalation: float = 0.06   # annual contractual increase
    inflation: float = 0.05            # for rand-denominated fee escalation

    @property
    def term_years(self) -> int:
        # para 4.3 -- RA with no specified term runs to age 55
        return RA_LAST_DISCLOSURE_AGE - self.entry_age

    def disclosure_periods(self) -> list[int]:
        return [1, 3, 5, self.term_years]


# ---------------------------------------------------------------------------
# The charge structure -- this is what train.py searches over
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChargeStructure:
    name: str = "unnamed"

    # --- investment management (para 5.1): TER + transaction costs -----------
    ter: float = 0.0095
    transaction_costs: float = 0.0015

    # --- advice (para 5.2) ---------------------------------------------------
    initial_advice_pct: float = 0.0330      # % of each premium, first `initial_advice_months`
    initial_advice_months: int = 12
    ongoing_advice_pct: float = 0.0050      # % p.a. of fund

    # --- administration (para 5.3) ------------------------------------------
    admin_fund_pct: float = 0.0050          # % p.a. of fund
    admin_fixed_monthly: float = 35.0       # rand p.m., escalates with inflation
    admin_premium_pct: float = 0.0          # % of each premium

    # --- other (para 5.4): termination charges, penalties, loyalty bonuses ---
    termination_pct: float = 0.0            # % of fund charged on early exit
    termination_taper_years: float = 5.0    # termination charge grades to zero over this
    loyalty_bonus_pct: float = 0.0          # % of fund added at each loyalty_bonus_years
    loyalty_bonus_years: tuple = ()

    # --- provenance ----------------------------------------------------------
    notes: str = ""
    external_benefit_pct: float = 0.0       # see gate G3 -- deliberately trapped

    # --- para 4.7: charges eligible for the SIMPLIFIED methodology -----------
    # (expressed as a % of value, deducted on a consistent ongoing basis, and
    #  level over the disclosure period) go in at their actual percentage.
    def simplified(self, component: str) -> float:
        if component == "imc":
            return self.ter + self.transaction_costs          # para 5.1
        if component == "advice":
            return self.ongoing_advice_pct                    # para 5.2.2
        if component == "admin":
            return self.admin_fund_pct                        # para 5.3
        return 0.0

    # --- para 4.9: everything else needs a single RIY calc per component ------
    def riy_part_off(self, component: str) -> "ChargeStructure":
        if component == "imc":
            return self
        if component == "advice":
            return replace(self, initial_advice_pct=0.0)
        if component == "admin":
            return replace(self, admin_fixed_monthly=0.0, admin_premium_pct=0.0)
        if component == "other":
            return replace(self, termination_pct=0.0, loyalty_bonus_pct=0.0)
        raise ValueError(component)

    def all_charges_off(self) -> "ChargeStructure":
        return replace(self, ter=0.0, transaction_costs=0.0,
                       initial_advice_pct=0.0, ongoing_advice_pct=0.0,
                       admin_fund_pct=0.0, admin_fixed_monthly=0.0,
                       admin_premium_pct=0.0,
                       termination_pct=0.0, loyalty_bonus_pct=0.0)


# ---------------------------------------------------------------------------
# Cash flow projection (para 6.1)
#
#   NAV[n] = NAV[t] * (1 + g_{t:n}) + sum(CF[n])
#   g_{t:n} = (1+g)^(days/365) - 1
#
# Monthly steps, premiums monthly in advance (para 6.2: contractual timing).
# ---------------------------------------------------------------------------

MONTH_DAYS = 365.0 / 12.0


@dataclass
class ProjectionResult:
    payout: float
    provider_charge_pv: float
    gross_premiums: float


def project(policy: Policy,
            cs: ChargeStructure,
            years: float,
            growth: float) -> ProjectionResult:
    """Roll the fund forward to `years` and terminate (para 4.3: the EAC assumes
    the investor terminates at the end of each disclosure period)."""
    months = int(round(years * 12))
    nav = 0.0
    charge_pv = 0.0          # PV of charges accruing to the provider, at PRESCRIBED_GROWTH
    gross_premiums = 0.0

    monthly_growth = (1.0 + growth) ** (MONTH_DAYS / 365.0) - 1.0
    fund_charge_annual = cs.ter + cs.transaction_costs + cs.ongoing_advice_pct + cs.admin_fund_pct
    # convert annual fund-based charge to an equivalent monthly deduction
    monthly_fund_charge = 1.0 - (1.0 - fund_charge_annual) ** (1.0 / 12.0)

    for m in range(months):
        year_index = m // 12
        disc = (1.0 + PRESCRIBED_GROWTH) ** (-(m * MONTH_DAYS) / 365.0)

        # --- premium in advance ---------------------------------------------
        premium = policy.monthly_premium * (1.0 + policy.premium_escalation) ** year_index
        gross_premiums += premium

        adv = premium * cs.initial_advice_pct if m < cs.initial_advice_months else 0.0
        adm_prem = premium * cs.admin_premium_pct
        nav += premium - adv - adm_prem
        charge_pv += (adv + adm_prem) * disc

        # --- fixed rand admin fee, escalating with inflation ------------------
        fixed = cs.admin_fixed_monthly * (1.0 + policy.inflation) ** year_index
        nav -= fixed
        charge_pv += fixed * disc

        # --- growth over the month -------------------------------------------
        nav *= (1.0 + monthly_growth)

        # --- fund-based charges ----------------------------------------------
        fee = nav * monthly_fund_charge
        nav -= fee
        charge_pv += fee * (1.0 + PRESCRIBED_GROWTH) ** (-((m + 1) * MONTH_DAYS) / 365.0)

        # --- loyalty bonus (para 5.4, an "other" item; reduces the charge) -----
        if cs.loyalty_bonus_pct and any(
                abs((m + 1) / 12.0 - y) < 1e-9 for y in cs.loyalty_bonus_years):
            bonus = nav * cs.loyalty_bonus_pct
            nav += bonus
            charge_pv -= bonus * (1.0 + PRESCRIBED_GROWTH) ** (-((m + 1) * MONTH_DAYS) / 365.0)

    # --- termination charge on exit (para 5.4) --------------------------------
    if cs.termination_pct and years < cs.termination_taper_years:
        taper = 1.0 - (years / cs.termination_taper_years)
        pen = nav * cs.termination_pct * taper
        nav -= pen
        charge_pv += pen * (1.0 + PRESCRIBED_GROWTH) ** (-years)

    return ProjectionResult(payout=nav, provider_charge_pv=charge_pv,
                            gross_premiums=gross_premiums)


# ---------------------------------------------------------------------------
# RIY methodology (para 6.3)
# ---------------------------------------------------------------------------

def _solve_reduced_growth(policy: Policy,
                          cs_without: ChargeStructure,
                          target_payout: float,
                          years: float) -> float:
    """para 6.3 Step 2: solve for the growth rate that, with this component's
    charges removed, reproduces the step-1 payout."""
    def f(g: float) -> float:
        return project(policy, cs_without, years, g).payout - target_payout

    lo, hi = -0.90, PRESCRIBED_GROWTH + 1e-9
    try:
        return brentq(f, lo, hi, xtol=1e-12, rtol=1e-14, maxiter=200)
    except ValueError:
        # payout not bracketed (e.g. component has zero charges) -> no reduction
        return PRESCRIBED_GROWTH


def eac_at(policy: Policy, cs: ChargeStructure, years: float) -> dict[str, float]:
    """Full four-component EAC at one disclosure period.

    para 4.9: simplified-eligible charges go in at face value; a single RIY
    calculation per component covers the rest; the two are added.
    para 6.4: the last component is the balancing item so the four sum to the
    total RIY, which absorbs the interaction between components.
    """
    # para 6.3 Step 1: payout including ALL charges
    payout_all = project(policy, cs, years, PRESCRIBED_GROWTH).payout

    # para 6.4: total RIY, from the no-charge projection
    g_total = _solve_reduced_growth(policy, cs.all_charges_off(), payout_all, years)
    riy_total = PRESCRIBED_GROWTH - g_total

    out: dict[str, float] = {}
    for comp in COMPONENTS:
        if comp == LAST_COMPONENT:
            continue
        simple = cs.simplified(comp)                       # para 4.7
        stripped = cs.riy_part_off(comp)
        if stripped == cs:
            riy = 0.0                                      # nothing needing RIY
        else:
            g_red = _solve_reduced_growth(policy, stripped, payout_all, years)
            riy = PRESCRIBED_GROWTH - g_red
        out[comp] = simple + riy

    out[LAST_COMPONENT] = riy_total - sum(out[c] for c in COMPONENTS if c != LAST_COMPONENT)
    out["total"] = riy_total
    return out


def eac_table(policy: Policy, cs: ChargeStructure) -> dict[int, dict[str, float]]:
    """The mandatory EAC table: four components at 1, 3, 5 years and term (para 4.3)."""
    return {p: eac_at(policy, cs, float(p)) for p in policy.disclosure_periods()}


def format_eac_table(policy: Policy, cs: ChargeStructure) -> str:
    tbl = eac_table(policy, cs)
    periods = policy.disclosure_periods()
    hdr = f"{'Impact of charges':<22}" + "".join(f"{str(p) + 'y':>10}" for p in periods)
    rows = [hdr, "-" * len(hdr)]
    labels = {"imc": "Investment management", "advice": "Advice",
              "admin": "Administration", "other": "Other"}
    for comp in COMPONENTS:
        rows.append(f"{labels[comp]:<22}" +
                    "".join(f"{tbl[p][comp] * 100:>9.2f}%" for p in periods))
    rows.append("-" * len(hdr))
    rows.append(f"{'Effective Annual Cost':<22}" +
                "".join(f"{tbl[p]['total'] * 100:>9.2f}%" for p in periods))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Acceptability gates -- the "IS IT ACCEPTABLE? Y/N" step
#
# These enforce the Standard's own anti-manipulation clauses. They are the
# reason this loop can be pointed at "make the EAC lower" without it becoming
# a disclosure-gaming machine.
# ---------------------------------------------------------------------------

REVENUE_TOLERANCE = 0.02       # provider PV must stay within +/-2% of baseline
CUMULATIVE_TOLERANCE = 0.03   # max drift from the ORIGINAL baseline
ARTEFACT_TOLERANCE = 0.20      # >20% of the headline gain must survive perturbation


@dataclass
class GateResult:
    passed: bool
    gate: str
    clause: str
    detail: str


def _off_disclosure_horizons(policy: Policy) -> list[float]:
    """Holding periods deliberately NOT on the mandatory measurement points."""
    t = policy.term_years
    return [h for h in (2.0, 4.0, 7.0, 12.0, t * 0.5, t * 0.8) if 0.5 < h < t]


def gate_revenue_neutral(policy: Policy,
                         baseline: ChargeStructure,
                         candidate: ChargeStructure) -> GateResult:
    """G1. Same revenue to the provider, or it is not a like-for-like comparison.

    A structure that lowers the EAC by lowering provider income is a pricing
    decision, not a research finding. It gets routed to the product team, not
    committed here.
    """
    t = float(policy.term_years)
    base_pv = project(policy, baseline, t, PRESCRIBED_GROWTH).provider_charge_pv
    cand_pv = project(policy, candidate, t, PRESCRIBED_GROWTH).provider_charge_pv
    delta = (cand_pv - base_pv) / base_pv
    ok = abs(delta) <= REVENUE_TOLERANCE

    # Cumulative guard: a run of individually-tolerable give-backs must not walk
    # the provider's income down over many experiments.
    drift_note = ""
    orig_pv = project(policy, BASELINE, t, PRESCRIBED_GROWTH).provider_charge_pv
    drift = (cand_pv - orig_pv) / orig_pv
    if abs(drift) > CUMULATIVE_TOLERANCE:
        ok = False
        drift_note = (f"; cumulative drift from the original baseline {drift * 100:+.2f}% "
                      f"exceeds +/-{CUMULATIVE_TOLERANCE * 100:.0f}%")
    return GateResult(
        passed=ok,
        gate="G1 revenue neutrality",
        clause="(internal constraint)",
        detail=f"provider charge PV {delta * 100:+.2f}% vs incumbent "
               f"(tolerance +/-{REVENUE_TOLERANCE * 100:.0f}%){drift_note}",
    )


def gate_not_a_disclosure_artefact(policy: Policy,
                                   baseline: ChargeStructure,
                                   candidate: ChargeStructure) -> GateResult:
    """G2. THE important one. Clause 3.1.6.2.

    "A Provider shall not manipulate any values or calculations ... to make a
     Financial Product appear less expensive."

    Test: the headline EAC saving is measured at the mandatory disclosure points
    under the prescribed 6% growth. If that saving evaporates when we move OFF
    those points -- other holding periods, other growth rates -- then the saving
    lives in the measurement convention, not in the investor's pocket.

    We compare real terminal value to the investor across a perturbation grid.
    """
    t = float(policy.term_years)

    periods = policy.disclosure_periods()
    headline_base = sum(eac_at(policy, baseline, float(p))["total"] for p in periods) / len(periods)
    headline_cand = sum(eac_at(policy, candidate, float(p))["total"] for p in periods) / len(periods)
    headline_gain = headline_base - headline_cand      # positive = candidate cheaper

    if headline_gain <= 0:
        return GateResult(False, "G2 artefact test", "3.1.6.2",
                          "candidate is not cheaper at the disclosure points")

    # Perturb: growth rates away from the prescribed 6%, holding periods away
    # from the mandatory measurement points.
    survived, tested = 0, 0
    worst = None
    for g in (0.02, 0.04, 0.06, 0.08, 0.10, 0.12):
        for h in _off_disclosure_horizons(policy):
            tested += 1
            b = project(policy, baseline, h, g).payout
            c = project(policy, candidate, h, g).payout
            rel = (c - b) / b if b else 0.0     # positive = investor better off
            if rel > 0:
                survived += 1
            if worst is None or rel < worst[0]:
                worst = (rel, g, h)

    share = survived / tested if tested else 0.0
    ok = share >= (1.0 - ARTEFACT_TOLERANCE)
    w_rel, w_g, w_h = worst
    return GateResult(
        passed=ok,
        gate="G2 artefact test",
        clause="3.1.6.2",
        detail=f"investor better off in {survived}/{tested} off-disclosure scenarios "
               f"({share * 100:.0f}%); worst case {w_rel * 100:+.2f}% terminal value "
               f"at g={w_g * 100:.0f}%, {w_h:.1f}y",
    )


def gate_no_external_benefit(policy: Policy,
                             baseline: ChargeStructure,
                             candidate: ChargeStructure) -> GateResult:
    """G3. Clause 3.1.16.

    Charge reductions that depend on a loyalty programme, a medical aid, another
    product, "or any other mechanism operating outside of the Financial Product"
    may NOT be taken into account in the EAC. They may only be mentioned in the
    free text notes.
    """
    ok = candidate.external_benefit_pct == 0.0
    return GateResult(
        passed=ok,
        gate="G3 external benefit",
        clause="3.1.16",
        detail="no out-of-product benefit relied on" if ok else
               f"relies on {candidate.external_benefit_pct * 100:.2f}% benefit accruing "
               f"outside the Financial Product -- may not reduce the EAC",
    )


def gate_charge_shifting_disclosed(policy: Policy,
                                   baseline: ChargeStructure,
                                   candidate: ChargeStructure) -> GateResult:
    """G4. Clauses 3.1.12 / 3.1.13.

    Moving a charge from one EAC component to another is permitted but must be
    explained in the free text notes. If the total is essentially unchanged and
    only the component split moved, that is charge-shifting and needs a note.
    """
    periods = policy.disclosure_periods()
    shifting = True
    worst_comp = 0.0
    for p in periods:
        b, c = eac_at(policy, baseline, float(p)), eac_at(policy, candidate, float(p))
        comp_move = max(abs(c[k] - b[k]) for k in COMPONENTS)
        worst_comp = max(worst_comp, comp_move)
        # charge-shifting only if the TOTAL is unchanged at every period while
        # the component split moves. If the total moves anywhere, the structure
        # genuinely differs and this is not a shift.
        if not (comp_move > 0.0015 and abs(c["total"] - b["total"]) < 0.0005):
            shifting = False
            break
    ok = (not shifting) or ("charge-shifting" in candidate.notes.lower())
    return GateResult(
        passed=ok,
        gate="G4 charge-shifting",
        clause="3.1.12 / 3.1.13",
        detail="no undisclosed component shift" if ok else
               f"components moved up to {worst_comp * 100:.2f}% at every disclosure "
               f"period while the total did not -- requires a free text note",
    )


GATES: tuple[Callable[[Policy, ChargeStructure, ChargeStructure], GateResult], ...] = (
    gate_revenue_neutral,
    gate_not_a_disclosure_artefact,
    gate_no_external_benefit,
    gate_charge_shifting_disclosed,
)


# ---------------------------------------------------------------------------
# The single metric + verdict. This is what the ratchet loop reads.
# ---------------------------------------------------------------------------

@dataclass
class Evaluation:
    name: str
    metric: float                      # mean EAC across the four disclosed periods
    table: dict[int, dict[str, float]]
    gates: list[GateResult]
    accepted: bool
    verdict: str
    notes: str = ""

    @property
    def failed_gates(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]


def evaluate(policy: Policy,
             incumbent: ChargeStructure,
             candidate: ChargeStructure) -> Evaluation:
    table = eac_table(policy, candidate)
    metric = sum(table[p]["total"] for p in policy.disclosure_periods()) / len(
        policy.disclosure_periods())

    # Gates compare the candidate against the INCUMBENT -- the structure
    # currently committed to main -- not against the original baseline.
    # Judging against the baseline lets a gaming move ride in on the back of
    # earlier honest gains: it still looks better than where we started.
    # Each experiment must stand on its own diff.
    results = [gate(policy, incumbent, candidate) for gate in GATES]
    accepted = all(r.passed for r in results)

    if accepted:
        verdict = "ACCEPT -- commit to main"
    else:
        first = next(r for r in results if not r.passed)
        if first.gate.startswith("G2"):
            verdict = "REJECT -- disclosure artefact, not a real saving"
        elif first.gate.startswith("G1"):
            verdict = "ROUTE TO PRODUCT -- changes provider revenue, not a like-for-like finding"
        else:
            verdict = f"REJECT -- {first.gate}"

    return Evaluation(name=candidate.name, metric=metric, table=table,
                      gates=results, accepted=accepted, verdict=verdict,
                      notes=candidate.notes)


def format_evaluation(policy: Policy,
                      baseline: ChargeStructure,
                      candidate: ChargeStructure,
                      ev: Evaluation) -> str:
    periods = policy.disclosure_periods()
    base_metric = sum(eac_at(policy, baseline, float(p))["total"] for p in periods) / len(periods)
    lines = [
        "=" * 74,
        f"CANDIDATE: {ev.name}",
        "=" * 74,
        "",
        "BASELINE",
        format_eac_table(policy, baseline),
        "",
        "CANDIDATE",
        format_eac_table(policy, candidate),
        "",
        f"metric (mean disclosed EAC): "
        f"{ev.metric * 100:.3f}%  vs baseline {base_metric * 100:.3f}%  "
        f"({(ev.metric - base_metric) * 100:+.3f}pp)",
        "",
        "ACCEPTABILITY GATES",
        "-" * 74,
    ]
    for g in ev.gates:
        mark = "PASS" if g.passed else "FAIL"
        lines.append(f"  [{mark}] {g.gate:<26} clause {g.clause}")
        lines.append(f"         {g.detail}")
    lines += ["", f"VERDICT: {ev.verdict}", ""]
    if ev.notes:
        lines += [f"note: {ev.notes}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The baseline: a conventional recurring-premium RA as sold today
# ---------------------------------------------------------------------------

BASELINE = ChargeStructure(
    name="baseline-RA",
    ter=0.0095,
    transaction_costs=0.0015,
    initial_advice_pct=0.0330,
    initial_advice_months=12,
    ongoing_advice_pct=0.0050,
    admin_fund_pct=0.0050,
    admin_fixed_monthly=35.0,
    termination_pct=0.0,
    notes="conventional recurring-premium RA, upfront advice fee over year 1",
)

POLICY = Policy()


if __name__ == "__main__":
    print(f"RA: entry age {POLICY.entry_age}, term to age {RA_LAST_DISCLOSURE_AGE} "
          f"({POLICY.term_years} years), R{POLICY.monthly_premium:,.0f}/month "
          f"escalating at {POLICY.premium_escalation * 100:.0f}% p.a.")
    print(f"Prescribed growth: {PRESCRIBED_GROWTH * 100:.0f}% (para 6.3)\n")
    print(format_eac_table(POLICY, BASELINE))
