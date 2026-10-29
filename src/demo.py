"""Public demo (triage.bigyan.work): two fixed demo runs, one live run at a time, recorded runs for replay.

The public site never takes a file path or model from the browser. A live run is started by demo id only, runs in a
background thread (so a visitor closing the tab cannot leave the lock held), is capped by the profile's turn limit and
a wall-clock limit, and is recorded. The newest completed recording is what the replay button plays.

Before every live run the shared state a run can change is reset: the demo's rule file is emptied, threshold.config is
restored, and log folders the model created with run_suricata are removed.
"""

import json
import os
import queue
import shutil
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from .engine import run_triage
from .profiles import PROFILES

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("DEMO_RUNS_DIR", ROOT / "demo-runs"))   # persistent volume on the server
SHIPPED_DIR = ROOT / "demo"                                              # recordings committed to the repo (fallback)
MODEL = os.environ.get("DEMO_MODEL", "deepseek-v4-pro")
WALL_LIMIT_S = int(os.environ.get("DEMO_WALL_LIMIT_S", 2700))   # 150 turns at ~13 s/turn ≈ 33 min
PER_IP_PER_HOUR = int(os.environ.get("DEMO_PER_IP_PER_HOUR", 3))
PER_DAY = int(os.environ.get("DEMO_PER_DAY", 40))
RULE = "-" * 72

DEMOS = {
    "cic": {"profile": "demo-cic", "log": "demo-cic", "pcap": "data/slices/demo-cic.pcap",
            "title": "CIC-IDS2017 · Friday slice"},
    "unsw": {"profile": "demo-unsw", "log": "demo-unsw", "pcap": "data/slices/demo-unsw.pcap",
             "title": "UNSW-NB15 · 22 Jan hold-out slice"},
}
for _d in DEMOS.values():
    _d["eve"] = f"logs/{_d['log']}/eve.json"
    _d["rule_file"] = PROFILES[_d["profile"]]["rule_file"]

_THRESHOLD = ROOT / "config" / "threshold.config"
_PRISTINE_THRESHOLD = _THRESHOLD.read_bytes() if _THRESHOLD.exists() else b""

_lock = threading.Lock()
_active = {"demo": None, "started": None}
_ip_hits = defaultdict(deque)
_day_hits = deque()


def demo_for(value: str):
    """Map what the UI sends (demo id or the demo's eve path) to a demo id; None if it is not a demo."""
    for demo_id, d in DEMOS.items():
        if value in (demo_id, d["eve"], f"demo:{demo_id}"):
            return demo_id
    return None


def available() -> dict:
    """Demos whose Suricata output exists in this deployment (a demo without its capture slice is not offered)."""
    return {k: v for k, v in DEMOS.items() if (ROOT / v["eve"]).exists() or latest_recording(k)}


def status() -> dict:
    return {"busy": _lock.locked(), "running": _active["demo"],
            "elapsed_s": int(time.time() - _active["started"]) if _active["started"] else None}


def _reset(demo_id: str):
    d = DEMOS[demo_id]
    (ROOT / d["rule_file"]).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / d["rule_file"]).write_text("")
    _THRESHOLD.write_bytes(_PRISTINE_THRESHOLD)
    logs = ROOT / "logs"
    keep = {x["log"] for x in DEMOS.values()}
    for p in logs.iterdir() if logs.exists() else ():
        if p.is_dir() and p.name not in keep:
            shutil.rmtree(p, ignore_errors=True)


def _rate_ok(ip: str) -> str:
    now = time.time()
    hits = _ip_hits[ip]
    while hits and now - hits[0] > 3600:
        hits.popleft()
    while _day_hits and now - _day_hits[0] > 86400:
        _day_hits.popleft()
    if len(hits) >= PER_IP_PER_HOUR:
        return "You have started the maximum live runs for this hour. Press Replay to watch a recorded run."
    if len(_day_hits) >= PER_DAY:
        return "Today's live-run budget is used up. Press Replay to watch a recorded run."
    hits.append(now)
    _day_hits.append(now)
    return ""


def start_live(demo_id: str, ip: str):
    """Start a live run in the background. Returns (queue, None) or (None, reason)."""
    if not _lock.acquire(blocking=False):
        return None, "Another visitor's live run is in progress. Press Replay to watch a recorded run, or try again in a few minutes."
    reason = _rate_ok(ip)
    if reason:
        _lock.release()
        return None, reason
    q = queue.Queue()
    threading.Thread(target=_run, args=(demo_id, q), daemon=True).start()
    return q, None


def _run(demo_id: str, q: queue.Queue):
    d = DEMOS[demo_id]
    started = datetime.now(timezone.utc)
    t0 = time.time()
    _active.update(demo=demo_id, started=t0)
    out = RUNS_DIR / demo_id / started.strftime("%Y%m%d-%H%M%S")
    completed = False
    try:
        _reset(demo_id)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "events.jsonl", "w") as rec:
            for ev in run_triage(d["eve"], model=MODEL, profile=d["profile"]):
                rec.write(json.dumps({"t": round(time.time() - t0, 2), "event": ev}) + "\n")
                rec.flush()
                q.put(ev)
                if ev.get("type") == "done":
                    completed = True
                if time.time() - t0 > WALL_LIMIT_S:
                    q.put({"type": "error", "message": f"Demo time limit ({WALL_LIMIT_S // 60} min) reached."})
                    break
    except Exception as e:  # never leave the lock held
        q.put({"type": "error", "message": f"Demo run failed: {e}"})
    finally:
        try:
            if out.exists():
                rules = ROOT / d["rule_file"]
                if rules.exists():
                    shutil.copy(rules, out / "ai_rules.rules")
                (out / "meta.json").write_text(json.dumps({
                    "demo": demo_id, "model": MODEL, "profile": d["profile"], "completed": completed,
                    "started": started.isoformat(timespec="seconds"), "duration_s": int(time.time() - t0)}))
                write_transcript(out)
        finally:
            _active.update(demo=None, started=None)
            _lock.release()
            q.put(None)


def latest_recording(demo_id: str):
    """Newest completed live recording for this demo, else the one shipped in the repo."""
    runs = sorted((RUNS_DIR / demo_id).glob("*/meta.json"), reverse=True) if (RUNS_DIR / demo_id).exists() else []
    for meta in runs:
        if json.loads(meta.read_text()).get("completed"):
            return meta.parent
    shipped = SHIPPED_DIR / demo_id
    return shipped if (shipped / "events.jsonl").exists() else None


def replay_events(demo_id: str, target_s: float = 90.0, max_gap: float = 1.2):
    """Yield (delay_s, event) from the latest recording, squeezed into about target_s seconds.

    Streamed text arrives as thousands of tiny deltas, so consecutive thinking/text deltas are merged into chunks
    (same text, far fewer events). Gaps longer than max_gap (the model waiting on the API) are cut to max_gap, then
    all gaps are scaled so the whole replay lasts about target_s, keeping the order and the rhythm of the run.
    """
    rec = latest_recording(demo_id)
    if not rec:
        yield 0, {"type": "error", "message": "No recorded run is available yet for this demo."}
        return
    merged = []  # [t, event]
    with open(rec / "events.jsonl") as f:
        for line in f:
            row = json.loads(line)
            ev = row["event"]
            prev = merged[-1][1] if merged else None
            if (prev and ev.get("type") in ("thinking", "text") and prev.get("type") == ev["type"]
                    and len(prev.get("text", "")) < 600):
                prev["text"] += ev.get("text", "")
                continue
            merged.append([row["t"], dict(ev)])
    gaps = [min(max(0.0, b[0] - a[0]), max_gap) for a, b in zip(merged, merged[1:])]
    scale = min(1.0, target_s / (sum(gaps) or 1.0))
    yield 0, merged[0][1]
    for gap, (_, ev) in zip(gaps, merged[1:]):
        yield gap * scale, ev


def write_transcript(run_dir: Path):
    """Readable transcript (same layout as src/batch_transcript.py) and the final report, from a recording."""
    meta = json.loads((run_dir / "meta.json").read_text()) if (run_dir / "meta.json").exists() else {}
    body, text_buf, report, turns, usage = [], [], "", 0, {"input_tokens": 0, "output_tokens": 0}

    def flush():
        if text_buf:
            body.append(f"\n[AGENT TEXT]\n{''.join(text_buf).strip()}\n")
            text_buf.clear()

    with open(run_dir / "events.jsonl") as f:
        for line in f:
            ev = json.loads(line)["event"]
            t = ev.get("type")
            if t == "text":
                text_buf.append(ev["text"])
            elif t == "tool_call":
                flush()
                body.append(f"{RULE}\n[TOOL CALL] {ev['name']}\n{json.dumps(ev['input'], indent=2)}")
            elif t == "tool_result":
                body.append(f"[TOOL RESULT] {ev['name']}\n{ev['output']}\n{RULE}")
            elif t == "suppress_proposal":
                body.append(f"[SUPPRESS PROPOSAL — not applied, needs human approval]\n{ev['content']}")
            elif t == "usage":
                flush()
                turns, usage = ev["turn"], ev
                body.append(f"\n--- Turn {turns} | {ev['input_tokens']:,} in / {ev['output_tokens']:,} out ---\n")
            elif t == "done":
                flush()
                report = ev.get("report") or ""
            elif t == "error":
                flush()
                body.append(f"\n[ERROR] {ev['message']}")
    flush()
    header = ["=" * 72, "IDS TRIAGE ENGINE — PUBLIC DEMO TRANSCRIPT", "=" * 72,
              f"Demo:     {meta.get('demo', run_dir.parent.name)} ({meta.get('profile', '')})",
              f"Model:    {meta.get('model', MODEL)}",
              f"Started:  {meta.get('started', '')}   Duration: {meta.get('duration_s', 0)} s   Turns: {turns}",
              f"Tokens:   {usage['input_tokens']:,} in / {usage['output_tokens']:,} out",
              "The model never sees the datasets' ground-truth labels.", "=" * 72]
    tail = [f"\n{'=' * 72}\n[FINAL REPORT]\n{'=' * 72}\n{report}\n"] if report else []
    (run_dir / "transcript.txt").write_text("\n".join(header) + "\n" + "\n".join(body) + "\n".join(tail))
    if report:
        (run_dir / "report.md").write_text(report)


def downloads(demo_id: str) -> list:
    """Files a visitor may download for a demo: the demo eve.json and the latest recording's outputs."""
    d = DEMOS[demo_id]
    files = []
    eve = ROOT / d["eve"]
    if eve.exists():
        files.append({"name": "eve.json (Suricata output for the slice)", "file": "eve.json", "size": eve.stat().st_size})
    rec = latest_recording(demo_id)
    for fname, label in (("report.md", "AI triage report"), ("ai_rules.rules", "Rules the AI wrote"),
                         ("transcript.txt", "Full transcript (every tool call)")):
        if rec and (rec / fname).exists():
            files.append({"name": label, "file": fname, "size": (rec / fname).stat().st_size})
    return files


def download_path(demo_id: str, fname: str):
    if fname == "eve.json":
        return ROOT / DEMOS[demo_id]["eve"]
    if fname in ("report.md", "ai_rules.rules", "transcript.txt"):
        rec = latest_recording(demo_id)
        return rec / fname if rec and (rec / fname).exists() else None
    return None
