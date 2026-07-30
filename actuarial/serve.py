"""
serve.py -- the dashboard backend. Standard library only, no dependencies.

    python serve.py            # http://localhost:8420

Reads whatever the loop has written and serves it. Records the reviewer's
accept/reject decisions to decisions.jsonl, which is the feedback the
recommender agent is meant to learn from.

The dashboard polls, so a background run shows up live. Leave `simulate.py` or
`run.py` going in another terminal and the staircase extends while you talk.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

HERE = Path(__file__).parent
UI = HERE / "ui"
PORT = 8420

EXPERIMENTS = HERE / "experiments.jsonl"
QUEUE = HERE / "review_queue.jsonl"
DECISIONS = HERE / "decisions.jsonl"
TRACKS = HERE / "tracks.json"
PAPERS = HERE / "queue.jsonl"          # written by ingest.py


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def state() -> dict:
    decisions = {d["id"]: d for d in jsonl(DECISIONS)}
    queue = []
    for item in jsonl(QUEUE):
        d = decisions.get(item["id"])
        if d:
            item = {**item, "status": d["verdict"], "reason": d.get("reason", ""),
                    "decided_at": d["ts"]}
        queue.append(item)

    papers = jsonl(PAPERS)[:6]
    tracks = json.loads(TRACKS.read_text()) if TRACKS.exists() else []
    return {
        "experiments": jsonl(EXPERIMENTS),
        "queue": queue,
        "tracks": tracks,
        "papers": papers,
        "decisions": list(decisions.values()),
        "server_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(UI), **kw)

    def log_message(self, fmt, *args):        # keep the terminal clean for the demo
        pass

    def _send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/state":
            return self._send_json(state())
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/decision":
            return self._send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "malformed JSON"}, 400)

        item_id = payload.get("id")
        verdict = payload.get("verdict")
        if not item_id or verdict not in ("accepted", "rejected"):
            return self._send_json(
                {"error": "id and verdict (accepted|rejected) are required"}, 400)
        if verdict == "rejected" and not (payload.get("reason") or "").strip():
            return self._send_json({"error": "a rejection needs a reason"}, 400)

        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "id": item_id,
            "verdict": verdict,
            "reason": (payload.get("reason") or "").strip(),
            "reviewer": payload.get("reviewer") or "basis writer",
        }
        with DECISIONS.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        return self._send_json({"ok": True, "recorded": record})


if __name__ == "__main__":
    print(f"ActAutoresearch dashboard  ->  http://localhost:{PORT}")
    print("serving", UI)
    print("ctrl-c to stop\n")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
