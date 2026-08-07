# autoresearch

Small single-product Python repo (Karpathy's `autoresearch`): a single-GPU LLM pretraining loop. Only three files matter — `prepare.py` (data + tokenizer, read-only), `train.py` (the model/optimizer/training loop the agent edits), and `program.md` (agent instructions). See `README.md` for the quick start and design.

## Cursor Cloud specific instructions

- Package manager is `uv` (already installed and on `PATH`). Standard commands live in `README.md`: `uv sync`, `uv run prepare.py`, `uv run train.py`. Don't duplicate them elsewhere.
- There is no lint or automated test suite in this repo (no test framework, no linter config). "Validating" means running the pipeline below, not running tests.
- `train.py` REQUIRES a single NVIDIA GPU. It fails at import on GPU-less machines because line ~21 calls `torch.cuda.get_device_capability()` and it loads FlashAttention-3 CUDA kernels; the whole script hardcodes `device="cuda"` with no CPU/MPS fallback. The standard Cursor Cloud VM has no GPU, so `uv run train.py` cannot run here — this is expected, not a setup bug. Only run it on a GPU host.
- `prepare.py` runs fully on CPU and is the way to validate setup without a GPU: `uv run prepare.py --num-shards <N>` (needs at least 2 shards: 1 train + 1 val). It downloads real shards from HuggingFace and trains a BPE tokenizer.
- Data + tokenizer cache lives at `~/.cache/autoresearch/` (outside the repo). It persists in the VM snapshot, so `prepare.py` is a no-op once populated. Delete that dir to force a fresh prep.
- Both `prepare.py` and the first `train.py` run need network access to `huggingface.co` (data shards + FA3 kernels).
- Per `program.md`: only `train.py` is meant to be edited; `prepare.py` (including the `evaluate_bpb` metric) is read-only, and `results.tsv` is intentionally left untracked.
