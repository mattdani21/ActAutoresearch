# ActAutoresearch

Karpathy's autoresearch loop pointed at the ASISA Standard on Effective Annual
Cost instead of a language model, with a dashboard for the humans who have to
sign off on what it finds.

## The mapping

| autoresearch | here |
|---|---|
| `prepare.py` fixed, defines the metric | `prepare.py` — the EAC engine **and the four acceptability gates** |
| `train.py` the agent rewrites it | `train.py` — the proposed charge structure |
| `program.md` the human writes it | `program.md` — the research brief and the rules |
| metric `val_bpb` | mean disclosed EAC across 1, 3, 5 yr and term to age 55 |
| ratchet: keep if loss improved | ratchet: keep if EAC improved **and** all four gates pass |

## The one change that matters

```
ARE MY EACs GETTING LOWER?   Y/N
  IF Y: WHY?
        IS IT ACCEPTABLE?    Y/N
          IF Y: COMMIT TO MAIN
```

"Acceptable" is four tests enforcing the Standard's own anti-manipulation
clauses, not a judgement call:

| gate | clause | asks |
|---|---|---|
| G1 revenue neutrality | internal | same provider charge PV, so it is like-for-like — and no cumulative drift |
| G2 artefact test | **3.1.6.2** | does the saving survive growth rates 2–12% and holding periods off the mandatory measurement points? |
| G3 external benefit | **3.1.16** | is the reduction funded outside the product? |
| G4 charge-shifting | **3.1.12 / 3.1.13** | did the component split move while the total did not? |

Two design points worth knowing, because both are easy to get wrong:

- **Gates judge each candidate against the incumbent, not the original
  baseline.** Judging against the baseline lets a gaming move ride in on the
  back of earlier honest gains — it still looks better than where you started.
- **The agent may not edit `prepare.py`.** An agent that can rewrite its own
  scoring function finds the lowest EAC in four minutes and every one of them is
  worthless. That separation is the governance argument.

## Run it

```bash
python prepare.py               # baseline EAC table
python simulate.py --n 80        # a real run: 80 evaluations through the real gates
python serve.py                  # dashboard at http://localhost:8420
python run.py                    # one ratchet step from train.py
python report.py > report.md      # the handoff for the basis writer
python ingest.py --days 7         # the literature lane (needs network)
```

For the demo: leave `simulate.py` running in one terminal and `serve.py` in
another. The dashboard polls every four seconds, so the staircase extends while
you talk.

## What the loop found

80 experiments, 12 kept, baseline 5.105% → 2.331% mean disclosed EAC. Almost all
of the gain is removing front-loading: the year-1 EAC on the baseline is 11.06%
against 2.38% at term, and nearly all of that gap is the RIY treatment of an
upfront advice charge over a small first-year fund.

61 of the 80 were rejected under clause 3.1.6.2 — the saving existed only where
the Standard takes its measurements. Those rejections are the output a reviewer
should actually read.

## Caveats to say out loud

Charge data is synthetic. The literature lane is real. Revenue neutrality is PV
of charges, not a profit model — new business strain and commission regulation
are out of scope and may dominate. Persistency is not modelled, so the claim
that most investors do not hold an RA to age 55 is asserted, not evidenced. The
engine is a clean-room implementation of the Standard for demonstration, not a
production EAC calculator.
