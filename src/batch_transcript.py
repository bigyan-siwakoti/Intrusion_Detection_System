"""Run one triage session unattended and save a transcript in the web UI's export layout.

Usage: python -m src.batch_transcript logs/<run>/eve.json --model deepseek-v4-pro --profile unsw-bare
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import run_triage
from .profiles import PROFILES

ROOT = Path(__file__).resolve().parent.parent
RULE = "-" * 72


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eve_path")
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--profile", "--dataset", dest="profile", default="cic", choices=sorted(PROFILES))
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    out = ROOT / f"triage-{started.strftime('%Y-%m-%d-%H-%M-%S')}-{args.profile}.txt"
    run_name = Path(args.eve_path).parent.name
    size_mb = (ROOT / args.eve_path).stat().st_size / 1e6

    body, text_buf, turns, report, status = [], [], 0, "", "completed"
    usage = {"input_tokens": 0, "output_tokens": 0}

    def flush_text():
        if text_buf:
            body.append(f"\n[AGENT TEXT]\n{''.join(text_buf).strip()}\n")
            text_buf.clear()

    for ev in run_triage(args.eve_path, model=args.model, profile=args.profile):
        t = ev["type"]
        if t == "text":
            text_buf.append(ev["text"])
        elif t == "tool_call":
            flush_text()
            body.append(f"{RULE}\n[TOOL CALL] {ev['name']}\n{json.dumps(ev['input'], indent=2)}")
        elif t == "tool_result":
            body.append(f"[TOOL RESULT] {ev['name']}\n{ev['output']}\n{RULE}")
        elif t == "suppress_proposal":
            body.append(f"[SUPPRESS PROPOSAL — not applied]\n{ev['content']}")
        elif t == "usage":
            flush_text()
            turns = ev["turn"]
            usage = ev
            body.append(f"\n--- Turn {turns} | {ev['input_tokens']:,} in / {ev['output_tokens']:,} out ---\n")
        elif t == "done":
            flush_text()
            report = ev.get("report") or ""
        elif t == "error":
            flush_text()
            status = "error"
            body.append(f"\n[ERROR] {ev['message']}")

    ended = datetime.now(timezone.utc)
    dur = int((ended - started).total_seconds())
    header = [
        "=" * 72, "IDS TRIAGE ENGINE — SESSION TRANSCRIPT", "=" * 72,
        f"Run:      {run_name} ({size_mb:.1f} MB)",
        f"Model:    {args.model}",
        f"Started:  {started.isoformat(timespec='milliseconds').replace('+00:00', 'Z')}",
        f"Ended:    {ended.isoformat(timespec='milliseconds').replace('+00:00', 'Z')}",
        f"Duration: {dur // 60}m {dur % 60}s",
        f"Turns:    {turns}",
        f"Dataset:  {args.profile}   Status: {status}   Tokens: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out",
        "Source:   unattended batch run (src/batch_transcript.py)",
        "=" * 72,
    ]
    tail = [f"\n{'=' * 72}\n[FINAL REPORT]\n{'=' * 72}\n{report}\n"] if report else []
    out.write_text("\n".join(header) + "\n" + "\n".join(body) + "\n".join(tail))
    print(f"{out.name}: {run_name} {status}, {turns} turns, {dur // 60}m {dur % 60}s")


if __name__ == "__main__":
    main()
