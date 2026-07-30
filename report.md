# Spike report: levelling the upfront advice charge on a recurring-premium RA

**For:** basis writer, go/no-go before lead actuary
**Status:** committed to main — 1 of 81 candidates this run
**Reproduce:** `git checkout level-advice && python run.py`

## Verdict

**Worth a product actuary's time.** Not a recommendation to change a product.

## The claim, stated falsifiably

Removing the year-1 upfront advice charge and recovering the identical present
value as a level ongoing charge lowers the disclosed EAC at every disclosure
period short of the full term, without reducing the provider's charge income,
and the saving is not an artefact of where the Standard takes its measurements.

## Method

ASISA Retail Standard on EAC (22 May 2020), RIY methodology per para 6.3, at
the prescribed 6% growth (para 6.3 step 3). Simplified methodology applied
where para 4.7 conditions are met; single RIY calculation per component
otherwise (para 4.9); last component derived as the balancing item (para 6.4).

Disclosure periods 1, 3, 5 years and term to age 55 (para 4.3).

**Policy:** entry age 35, R2,500/month escalating at
6% p.a., 20-year term. **Synthetic.**

## Result

**Baseline**

| Impact of charges | 1 yr | 3 yr | 5 yr | 20 yr |
|---|---:|---:|---:|---:|
| Investment management | 1.10% | 1.10% | 1.10% | 1.10% |
| Advice | 6.95% | 1.26% | 0.77% | 0.52% |
| Administration | 3.31% | 1.48% | 1.09% | 0.65% |
| Other | -0.30% | 0.07% | 0.10% | 0.12% |
| **Effective Annual Cost** | **11.06%** | **3.91%** | **3.07%** | **2.38%** |

**Candidate**

| Impact of charges | 1 yr | 3 yr | 5 yr | 20 yr |
|---|---:|---:|---:|---:|
| Investment management | 1.10% | 1.10% | 1.10% | 1.10% |
| Advice | 0.51% | 0.51% | 0.51% | 0.51% |
| Administration | 3.21% | 1.46% | 1.09% | 0.65% |
| Other | 0.07% | 0.11% | 0.11% | 0.12% |
| **Effective Annual Cost** | **4.90%** | **3.19%** | **2.81%** | **2.38%** |

Mean disclosed EAC 5.105% → 3.320% (-1.785pp).
Year-1 EAC 11.06% → 4.90%.

Provider charge PV R115,333 → R115,331 (-0.00%).

## Acceptability

- **G1 revenue neutrality** (clause (internal constraint)) — PASS. provider charge PV -0.00% vs incumbent (tolerance +/-2%)
- **G2 artefact test** (clause 3.1.6.2) — PASS. investor better off in 36/36 off-disclosure scenarios (100%); worst case +0.03% terminal value at g=2%, 16.0y
- **G3 external benefit** (clause 3.1.16) — PASS. no out-of-product benefit relied on
- **G4 charge-shifting** (clause 3.1.12 / 3.1.13) — PASS. no undisclosed component shift

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

- **3% bonus at the 4 disclosure points** — metric 0.800%, failed clause 3.1.6.2
- **ongoing advice -0.10% (no offset)** — metric 2.225%, failed clause (internal constraint)
- **ongoing advice -0.05% (no offset)** — metric 2.278%, failed clause (internal constraint)

All failures by clause — 3.1.6.2: 61, (internal constraint): 7.

The rejections under clause 3.1.6.2 are the ones worth reading. Several scored
better on the metric than the candidate above and were reverted anyway, because
the saving existed only where the Standard takes its measurements.

