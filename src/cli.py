#!/usr/bin/env python3
"""CLI runner for the IDS triage engine. For testing before the web UI."""

import sys
import json
import argparse
from .engine import run_triage
from .profiles import PROFILES


BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def main():
    parser = argparse.ArgumentParser(description="Run AI triage on Suricata alerts")
    parser.add_argument("eve_path", help="Path to eve.json relative to project root")
    parser.add_argument("--model", default="claude-opus-5", help="Claude model to use")
    parser.add_argument("--profile", "--dataset", dest="profile", choices=sorted(PROFILES), default="cic",
                        help="Experiment profile (src/profiles.py): prompt, tools, Suricata config, rule file")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Auto-approve suppress proposals (for testing only)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON events instead of formatted text")
    args = parser.parse_args()

    approve_fn = (lambda fp, c: True) if args.auto_approve else None

    print(f"{BOLD}IDS Triage Engine{RESET}")
    print(f"Analysing: {args.eve_path}")
    print(f"Model: {args.model}")
    print(f"Profile: {args.profile} — {PROFILES[args.profile]['description']}")
    print(f"{'─' * 60}\n")

    try:
        for event in run_triage(args.eve_path, model=args.model,
                                approve_suppress=approve_fn, profile=args.profile):
            if args.json:
                print(json.dumps(event), flush=True)
                continue

            t = event["type"]

            if t == "thinking":
                print(f"{DIM}{event['text']}{RESET}", end="", flush=True)
            elif t == "thinking_start":
                print(f"\n{DIM}[thinking...]{RESET}\n", flush=True)
            elif t == "text_start":
                print(f"\n{GREEN}", end="", flush=True)
            elif t == "text":
                print(f"{event['text']}", end="", flush=True)
            elif t == "tool_call":
                inp = json.dumps(event["input"], indent=2) if event["input"] else ""
                print(f"\n{RESET}{BLUE}▶ {event['name']}{RESET}", flush=True)
                if inp:
                    for line in inp.split("\n"):
                        print(f"  {DIM}{line}{RESET}")
            elif t == "tool_result":
                output = event["output"]
                lines = output.split("\n")
                if len(lines) > 20:
                    preview = "\n".join(lines[:20])
                    print(f"  {DIM}{preview}\n  ... ({len(lines)} lines total){RESET}")
                else:
                    print(f"  {DIM}{output}{RESET}")
            elif t == "suppress_proposal":
                print(f"\n{YELLOW}{'─' * 60}")
                print(f"⚠ SUPPRESS PROPOSAL (requires approval):")
                print(f"  File: {event['file_path']}")
                print(f"  Content: {event['content']}")
                if approve_fn:
                    print(f"  → Auto-approved (testing mode)")
                else:
                    print(f"  → BLOCKED: needs human approval via web UI")
                print(f"{'─' * 60}{RESET}\n")
            elif t == "usage":
                print(f"\n{DIM}[Turn {event['turn']}: {event['input_tokens']} input + {event['output_tokens']} output tokens]{RESET}")
            elif t == "done":
                print(f"{RESET}\n\n{'═' * 60}")
                print(f"{BOLD}TRIAGE COMPLETE{RESET}")
                print(f"{'═' * 60}")
            elif t == "error":
                print(f"\n{RED}ERROR: {event['message']}{RESET}")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
