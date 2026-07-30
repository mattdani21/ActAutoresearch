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

**Requirements:** Python 3.10+ and [uv](https://docs.astral.sh/uv/). The only
dependency is SciPy — the RIY root-solve needs `brentq`. The dashboard is
standard library only.

```bash
uv sync                       # install (once)

uv run prepare.py             # baseline EAC table
uv run train.py               # evaluate the current proposal against the gates
uv run run.py                 # one ratchet step from train.py
uv run run.py --demo          # the four pre-baked candidates in candidates.py
uv run simulate.py --n 80     # a real run: 80 evaluations through the real gates
uv run serve.py               # dashboard at http://localhost:8420
uv run report.py > report.md  # the handoff for the basis writer
uv run ingest.py --days 7     # the literature lane (needs network)
```

## The demo: a loop that keeps running

Two terminals. The dashboard first, then the loop:

```bash
uv run serve.py                              # terminal 1 — http://localhost:8420
uv run simulate.py --forever --interval 5    # terminal 2 — until you ctrl-c it
```

`--forever` keeps proposing structures indefinitely; `--interval 5` paces them
at one every five seconds. Each experiment is appended to `experiments.jsonl`
the moment it is evaluated, and the dashboard polls every four seconds, so the
staircase extends and the review lane fills while you talk. Ctrl-C stops it and
prints the summary.

Pick the interval for the room. Unpaced, 80 experiments take about ten seconds
— fine for generating a log, useless to watch. At five seconds you get roughly
one new point per poll, which is about the rate a person can narrate.

What to point at while it runs:

- Most points are grey. The loop rejects far more than it keeps — 61 of the 80
  in the checked-in run failed clause **3.1.6.2** alone.
- A rejected point sitting *below* the current best is the argument for the
  whole architecture: it scored better and was reverted anyway, because the
  saving was only there where the Standard takes its measurements.
- The best-so-far line only ever steps down, and only through a structure that
  cleared all four gates.

`--n 80` without `--interval` is still the way to regenerate the checked-in log;
it produces exactly the run in `experiments.jsonl` today, timestamped as though
each experiment took six minutes.

## Layout

```
prepare.py         — the EAC engine and the four gates (agent must not modify)
train.py           — the proposed charge structure (the one file the agent edits)
program.md         — the research brief and the rules (the human edits this)
run.py             — the ratchet: lower? why? acceptable? commit or revert
simulate.py        — generates a full run of real evaluations
candidates.py      — four hand-built structures: one honest, three that game a clause
report.py          — the spike report for the basis writer
ingest.py          — ranks new arXiv papers against the department's rubric
serve.py           — dashboard backend, standard library only
ui/index.html      — the dashboard
experiments.jsonl  — the log of a completed 80-experiment run
review_queue.jsonl — what a human is asked to sign off on
tracks.json        — the department's research tracks, as shown in the dashboard
report.md          — a generated spike report, checked in as an example
```

`run.py` and `serve.py` also write `best.json`, `decisions.jsonl` and
`queue.jsonl`. Those are loop state, not source, and are gitignored.

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

## Provenance

The loop structure is Karpathy's
[autoresearch](https://github.com/karpathy/autoresearch) — fixed scorer, one
agent-editable file, a Markdown program the human iterates on, a ratchet that
keeps or discards. Everything measured here is the EAC engine, not a language
model, and the ratchet has a second condition the original does not need.

## License

MIT
