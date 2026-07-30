# Research programme: RA charge structure under the ASISA EAC Standard

You are running autonomous research on the charge structure of a
recurring-premium Retirement Annuity, measured under the ASISA Retail Standard
on Effective Annual Cost (22 May 2020).

## The loop

1. Read `experiments.jsonl` for what has already been tried and why it was
   rejected. Do not repeat a rejected structure.
2. Form a hypothesis. Write it into the `notes` field of the candidate.
3. Edit **`train.py` only**. Change `CANDIDATE`.
4. Run `python run.py`.
5. If the action is COMMIT, `git commit`. If REVERT, `git checkout train.py`
   and try something else.

## What you are optimising

`metric` = the mean of the four EAC values that would be **disclosed** under the
Standard: 1, 3, 5 years, and term to age 55 (para 4.3). Lower is better.

The baseline is 5.105%.

## What you may not do

`prepare.py` is fixed. It defines the measure and the four acceptability gates.
You may read it. You may not edit it, and you may not add code to `train.py`
that reaches into it, monkey-patches it, or bypasses `evaluate()`.

This is not a formality. The gates enforce the Standard's own anti-manipulation
clauses:

- **3.1.6.2** — a provider shall not manipulate any values or calculations to
  make a financial product appear less expensive.
- **3.1.16** — charge reductions arising from a loyalty programme, a medical
  aid, another product, or any other mechanism operating outside the financial
  product may not be taken into account in the EAC.
- **3.1.12 / 3.1.13** — moving a charge between EAC components, or onto another
  product, must be explained in the free text notes.

An agent that could edit its own scoring function would find the lowest EAC in
about four minutes and every one of them would be worthless. The separation is
the point.

## The test that matters

Gate G2 asks whether a saving is real or an artefact of where the Standard
takes its measurements. It recomputes the investor's terminal value across
growth rates from 2% to 12% and holding periods that deliberately avoid the
mandatory disclosure points.

A real saving survives that. An artefact does not.

Structures that concentrate value at 1, 3, 5 or 20 years exactly — vesting
bonuses, tapering penalties that expire on an anniversary, charge holidays —
will improve the metric and fail G2. They have already been tried. See
`anniversary-bonus` in the log: it scored **better than the current best**
and was reverted.

## Directions worth exploring

- The year-1 EAC is 11.06% against a full-term 2.38%. Almost all of that is the
  RIY treatment of front-loaded charges over a small fund. What else is
  front-loaded that need not be?
- Rand-denominated fees behave very differently from percentage fees across
  fund sizes. Where does that help the investor rather than just move the
  number?
- The Standard measures termination at each disclosure point (para 4.3). Real
  persistency does not look like that. Which structures are robust to the gap?
- Charges expressed as a percentage of premium versus a percentage of fund
  diverge as the fund grows. Is there a split that is genuinely cheaper for the
  median holding period rather than the disclosed ones?

## Constraint

Revenue neutrality (G1). A structure that lowers the EAC by lowering provider
income is a pricing decision, not a research finding — it gets routed to the
product team rather than committed. Hold the provider's charge PV within 2% of
baseline so the comparison is like-for-like.
