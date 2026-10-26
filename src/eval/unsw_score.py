"""Score Suricata alerts against the UNSW-NB15 ground truth (NUSW-NB15_GT.csv).

An attack event counts as detected when at least one alert shares its endpoints
(IPs + ports for TCP/UDP, IPs only for other protocols) and falls inside the
event's [start - tol, last + tol] window.

Usage: python -m src.eval.unsw_score [--tol 2]
"""

import argparse
import bisect
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GT_CSV = ROOT / "data/labels/source trouth unsw/NUSW-NB15_GT.csv"
PCAPS = [1, 3, 4, 5, 10, 14]
ATTACKER_NET = "175.45.176."
OUT = ROOT / "docs/results/unsw_scores.json"

RULESETS = {
    "stock": ("raw", lambda sid, custom: sid not in custom),
    "stock+cic": ("raw", lambda sid, custom: True),
    "stock+cic+unsw": ("final", lambda sid, custom: True),
}


def custom_sids() -> dict:
    """SID -> rule file for every AI-authored rule."""
    sids = {}
    for f in (ROOT / "rules/generated").rglob("*.rules"):
        for m in re.finditer(r"sid:(\d+);", f.read_text()):
            sids.setdefault(int(m.group(1)), f.name)
    return sids


def pcap_window(n: int) -> tuple:
    """First/last capture epoch from the raw run's events. Stats events carry replay wall-clock time, so skip them."""
    lo, hi = float("inf"), 0.0
    with open(ROOT / f"logs/unsw-{n}-raw/eve.json") as fh:
        for line in fh:
            ev = json.loads(line)
            if ev.get("event_type") == "stats":
                continue
            ts = datetime.fromisoformat(ev["timestamp"]).timestamp()
            lo, hi = min(lo, ts), max(hi, ts)
    return lo, hi


def load_gt(lo: float, hi: float) -> list:
    events = []
    with open(GT_CSV, encoding="latin-1") as fh:
        for r in csv.DictReader(fh):
            start, last = int(r["Start time"]), int(r["Last time"])
            if start < lo - 1 or start > hi + 1:
                continue
            cat = r["Attack category"].strip()
            if cat == "Backdoors":
                cat = "Backdoor"
            proto = r["Protocol"].strip().lower()
            events.append({
                "start": start, "last": last, "cat": cat, "proto": proto,
                "src": r["Source IP"], "sport": r["Source Port"],
                "dst": r["Destination IP"], "dport": r["Destination Port"],
            })
    return events


def key_of(a_ip, a_port, b_ip, b_port, portful: bool):
    if portful:
        ends = sorted([(a_ip, str(a_port)), (b_ip, str(b_port))])
    else:
        ends = sorted([(a_ip, ""), (b_ip, "")])
    return (portful,) + tuple(ends)


def index_gt(events: list) -> dict:
    idx = defaultdict(list)
    for i, e in enumerate(events):
        portful = e["proto"] in ("tcp", "udp")
        idx[key_of(e["src"], e["sport"], e["dst"], e["dport"], portful)].append(i)
    return idx


def load_alerts(path: Path) -> list:
    alerts = []
    with open(path) as fh:
        for line in fh:
            ev = json.loads(line)
            if ev.get("event_type") != "alert":
                continue
            alerts.append({
                "ts": datetime.fromisoformat(ev["timestamp"]).timestamp(),
                "sid": ev["alert"]["signature_id"],
                "src": ev.get("src_ip", ""), "sport": ev.get("src_port", ""),
                "dst": ev.get("dest_ip", ""), "dport": ev.get("dest_port", ""),
                "proto": (ev.get("proto") or "").lower(),
            })
    return alerts


def match(alerts, events, idx, tol):
    """Returns (set of detected event indices, per-alert list of matched event index or None)."""
    detected, per_alert = set(), []
    for a in alerts:
        portful = a["proto"] in ("tcp", "udp")
        hit = None
        for i in idx.get(key_of(a["src"], a["sport"], a["dst"], a["dport"], portful), []):
            e = events[i]
            if e["start"] - tol <= a["ts"] <= e["last"] + tol:
                detected.add(i)
                hit = i
        per_alert.append(hit)
    return detected, per_alert


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=2.0, help="seconds of slack around each GT event")
    args = ap.parse_args()

    custom = custom_sids()
    totals = Counter()
    totals_tcpudp = Counter()
    det = {rs: Counter() for rs in RULESETS}
    det_tcpudp = {rs: Counter() for rs in RULESETS}
    unmatched = {rs: Counter() for rs in RULESETS}
    alert_counts = Counter()
    rule_stats = defaultdict(lambda: {"alerts": 0, "matched": 0, "attacker_involved": 0,
                                      "cats": Counter(), "pcaps_fired": set()})

    for n in PCAPS:
        lo, hi = pcap_window(n)
        events = load_gt(lo, hi)
        idx = index_gt(events)
        for e in events:
            totals[e["cat"]] += 1
            if e["proto"] in ("tcp", "udp"):
                totals_tcpudp[e["cat"]] += 1

        for rs, (logname, keep) in RULESETS.items():
            alerts = [a for a in load_alerts(ROOT / f"logs/unsw-{n}-{logname}/eve.json")
                      if keep(a["sid"], custom)]
            alert_counts[rs] += len(alerts)
            detected, per_alert = match(alerts, events, idx, args.tol)
            for i in detected:
                det[rs][events[i]["cat"]] += 1
                if events[i]["proto"] in ("tcp", "udp"):
                    det_tcpudp[rs][events[i]["cat"]] += 1
            for a, hit in zip(alerts, per_alert):
                attacker = a["src"].startswith(ATTACKER_NET) or a["dst"].startswith(ATTACKER_NET)
                if hit is None:
                    unmatched[rs]["attacker_involved" if attacker else "no_attacker"] += 1
                if rs == "stock+cic+unsw" and a["sid"] in custom:
                    s = rule_stats[a["sid"]]
                    s["alerts"] += 1
                    s["attacker_involved"] += attacker
                    s["pcaps_fired"].add(n)
                    if hit is not None:
                        s["matched"] += 1
                        s["cats"][events[hit]["cat"]] += 1

    cats = sorted(totals)
    print(f"Tolerance ±{args.tol}s | pcaps {PCAPS} | GT events {sum(totals.values())} "
          f"({sum(totals_tcpudp.values())} TCP/UDP)\n")
    for label, tot, d in (("ALL PROTOCOLS", totals, det), ("TCP/UDP ONLY", totals_tcpudp, det_tcpudp)):
        print(f"== Event recall, {label}")
        print(f"{'category':<16}{'events':>8}" + "".join(f"{rs:>16}" for rs in RULESETS))
        for c in cats + ["TOTAL"]:
            t = sum(tot.values()) if c == "TOTAL" else tot[c]
            row = f"{c:<16}{t:>8}"
            for rs in RULESETS:
                v = sum(d[rs].values()) if c == "TOTAL" else d[rs][c]
                row += f"{v:>8} {100 * v / t if t else 0:5.1f}%"
            print(row)
        print()

    print("== Alerts not matching any GT event")
    for rs in RULESETS:
        u = unmatched[rs]
        print(f"{rs:<16} alerts {alert_counts[rs]:>6}  unmatched: attacker-involved {u['attacker_involved']:>5}"
              f"  no-attacker {u['no_attacker']:>5}")
    print()

    print("== AI-authored rules (stock+cic+unsw runs)")
    print(f"{'sid':>8}  {'file':<40}{'alerts':>7}{'GT-match':>9}{'atk-inv':>8}  pcaps  top categories")
    for sid in sorted(rule_stats):
        s = rule_stats[sid]
        top = ", ".join(f"{c}:{v}" for c, v in s["cats"].most_common(3))
        print(f"{sid:>8}  {custom[sid]:<40}{s['alerts']:>7}{s['matched']:>9}{s['attacker_involved']:>8}"
              f"  {len(s['pcaps_fired'])}/6   {top}")
    silent = sorted(set(custom) - set(rule_stats))
    print(f"\nAI rules loaded but never fired on UNSW: {len(silent)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "tolerance_s": args.tol, "pcaps": PCAPS,
        "gt_events": totals, "gt_events_tcpudp": totals_tcpudp,
        "detected": det, "detected_tcpudp": det_tcpudp,
        "alerts": alert_counts, "unmatched": unmatched,
        "ai_rules": {sid: {**s, "cats": dict(s["cats"]), "pcaps_fired": sorted(s["pcaps_fired"]),
                           "file": custom[sid]} for sid, s in rule_stats.items()},
    }, indent=2, default=dict))
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
