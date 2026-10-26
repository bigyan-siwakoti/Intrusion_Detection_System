"""Score Suricata alerts against the CIC-IDS2017 per-flow labels (TrafficLabelling CSVs).

A labelled flow counts as detected when at least one alert shares its 5-tuple (either
direction) and falls inside [start - tol, start + duration + tol]. CSV timestamps are
minute-resolution, 12-hour without AM/PM, in ADT (UTC-3).

Suricata engine/decoder/protocol-anomaly events (SIDs 2200000-2299999, "SURICATA ...")
are excluded from the stock baseline: in raw runs they fire on nearly every packet
(e.g. invalid checksum) and would count every flow as detected.

Tuesday and Thursday were replayed with every CIC rule loaded (config/cic/all-rules.yaml).
The Wednesday and Friday pcaps are no longer on disk, so their AI-authored rules are scored
from the triage-era logs in which they fired.

Usage: python -m src.eval.cic_score [--tol 120]
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "data/labels/TrafficLabelling"
OUT = ROOT / "docs/results/cic_scores.json"
ADT = timezone(timedelta(hours=-3))
PROTO = {"6": "tcp", "17": "udp"}
DELETED_AI_SIDS = {3000001: "wednesday_slowloris.rules (deleted)", 3000002: "wednesday_slowloris.rules (deleted)"}

DAYS = {
    "Tuesday": {
        "labels": ["Tuesday-WorkingHours.pcap_ISCX.csv"],
        "stock": "tuesday-all-rules-raw",
        "ai_logs": ["tuesday-all-rules-raw"],
    },
    "Wednesday": {
        "labels": ["Wednesday-workingHours.pcap_ISCX.csv"],
        "stock": "wednesday-raw",
        "ai_logs": ["wednesday-raw", "wednesday-final-validate2", "wednesday-validate-getflood"],
    },
    "Thursday": {
        "labels": ["Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
                   "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv"],
        "stock": "thursday-all-rules-raw",
        "ai_logs": ["thursday-all-rules-raw"],
    },
    "Friday": {
        "labels": ["Friday-WorkingHours-Morning.pcap_ISCX.csv",
                   "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
                   "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv"],
        "stock": "friday-raw",
        "ai_logs": ["friday-raw", "friday-botnet-validate2", "friday-validate-rules-loaded",
                    "friday-validate-rules-v3"],
    },
}


def custom_sids() -> dict:
    sids = dict(DELETED_AI_SIDS)
    for f in (ROOT / "rules/generated").rglob("*.rules"):
        for m in re.finditer(r"sid:(\d+);", f.read_text()):
            sids.setdefault(int(m.group(1)), f.name)
    return sids


def is_engine_event(sid: int) -> bool:
    return 2200000 <= sid <= 2299999


def parse_ts(s: str) -> float:
    date, clock = s.strip().split(" ")
    d, m, y = (int(x) for x in date.split("/"))
    hh, mm = (int(x) for x in clock.split(":")[:2])
    if hh < 8:
        hh += 12
    return datetime(y, m, d, hh, mm, tzinfo=ADT).timestamp()


def norm_label(s: str) -> str:
    s = s.strip()
    s = re.sub(r"Web Attack\s*\W+\s*", "Web Attack - ", s)
    return s


def load_flows(files: list) -> list:
    flows = []
    for name in files:
        with open(LABELS / name, encoding="latin-1") as fh:
            rd = csv.reader(fh)
            header = [h.strip() for h in next(rd)]
            ix = {h: i for i, h in enumerate(header)}
            for r in rd:
                if len(r) < len(header) or not r[ix["Timestamp"]].strip():
                    continue
                proto = PROTO.get(r[ix["Protocol"]].strip())
                if proto is None:
                    continue
                start = parse_ts(r[ix["Timestamp"]])
                dur = max(float(r[ix["Flow Duration"]] or 0), 0) / 1e6
                flows.append((r[ix["Source IP"]].strip(), r[ix["Source Port"]].strip(),
                              r[ix["Destination IP"]].strip(), r[ix["Destination Port"]].strip(),
                              proto, start, start + dur, norm_label(r[ix["Label"]])))
    return flows


def key_of(a_ip, a_port, b_ip, b_port, proto):
    return (proto,) + tuple(sorted([(a_ip, str(a_port)), (b_ip, str(b_port))]))


def iter_alerts(log: str):
    with open(ROOT / "logs" / log / "eve.json") as fh:
        for line in fh:
            if '"event_type":"alert"' not in line:
                continue
            ev = json.loads(line)
            proto = (ev.get("proto") or "").lower()
            if proto not in ("tcp", "udp"):
                continue
            yield {
                "ts": datetime.fromisoformat(ev["timestamp"]).timestamp(),
                "sid": ev["alert"]["signature_id"],
                "key": key_of(ev.get("src_ip"), ev.get("src_port"), ev.get("dest_ip"), ev.get("dest_port"), proto),
                "raw": (ev["timestamp"], ev.get("src_ip"), ev.get("src_port"), ev.get("dest_ip"), ev.get("dest_port")),
            }


def match_alert(a, flows, idx, tol):
    hits = [i for i in idx.get(a["key"], []) if flows[i][5] - tol <= a["ts"] <= flows[i][6] + tol]
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=120.0, help="seconds of slack (labels are minute-resolution)")
    args = ap.parse_args()
    custom = custom_sids()

    results = {"tolerance_s": args.tol, "days": {}, "ai_rules": {}}
    rule_stats = defaultdict(lambda: {"alerts": 0, "attack": 0, "benign": 0, "unmatched": 0, "labels": Counter()})

    for day, cfg in DAYS.items():
        flows = load_flows(cfg["labels"])
        idx = defaultdict(list)
        for i, f in enumerate(flows):
            idx[key_of(f[0], f[1], f[2], f[3], f[4])].append(i)
        totals = Counter(f[7] for f in flows)

        stock_det, stock_alerts = set(), Counter()
        for a in iter_alerts(cfg["stock"]):
            if a["sid"] in custom or is_engine_event(a["sid"]):
                continue
            hits = match_alert(a, flows, idx, args.tol)
            stock_det.update(hits)
            lab = "unmatched" if not hits else ("attack" if any(flows[i][7] != "BENIGN" for i in hits) else "benign")
            stock_alerts[lab] += 1

        ai_det, seen = set(), set()
        for log in cfg["ai_logs"]:
            for a in iter_alerts(log):
                if a["sid"] not in custom or (a["sid"], a["raw"]) in seen:
                    continue
                seen.add((a["sid"], a["raw"]))
                hits = match_alert(a, flows, idx, args.tol)
                ai_det.update(hits)
                s = rule_stats[a["sid"]]
                s["alerts"] += 1
                if not hits:
                    s["unmatched"] += 1
                else:
                    attack_labels = [flows[i][7] for i in hits if flows[i][7] != "BENIGN"]
                    if attack_labels:
                        s["attack"] += 1
                        s["labels"][Counter(attack_labels).most_common(1)[0][0]] += 1
                    else:
                        s["benign"] += 1

        det_stock = Counter(flows[i][7] for i in stock_det)
        det_both = Counter(flows[i][7] for i in stock_det | ai_det)
        results["days"][day] = {"flows": totals, "detected_stock": det_stock, "detected_stock_ai": det_both,
                                "stock_alerts": stock_alerts, "ai_rules_scored": bool(cfg["ai_logs"])}

        print(f"\n== {day}  (stock log: {cfg['stock']}; AI-rule logs: {', '.join(cfg['ai_logs']) or 'none'})")
        print(f"   stock alerts on attack flows {stock_alerts['attack']}, on benign flows {stock_alerts['benign']}, "
              f"unmatched {stock_alerts['unmatched']}")
        print(f"   {'label':<30}{'flows':>9}{'stock':>16}{'stock+AI':>16}")
        for lab in sorted(totals, key=lambda x: (x == "BENIGN", x)):
            t = totals[lab]
            print(f"   {lab:<30}{t:>9}{det_stock[lab]:>8} {100 * det_stock[lab] / t:5.1f}%"
                  f"{det_both[lab]:>8} {100 * det_both[lab] / t:5.1f}%")

    print("\n== AI-authored rules (Wednesday + Friday logs)")
    print(f"{'sid':>8}  {'file':<36}{'alerts':>7}{'attack':>8}{'benign':>8}{'unmatch':>8}  labels")
    for sid in sorted(rule_stats):
        s = rule_stats[sid]
        labs = ", ".join(f"{k}:{v}" for k, v in s["labels"].most_common(3))
        print(f"{sid:>8}  {custom[sid]:<36}{s['alerts']:>7}{s['attack']:>8}{s['benign']:>8}{s['unmatched']:>8}  {labs}")
        results["ai_rules"][sid] = {**s, "labels": dict(s["labels"]), "file": custom[sid]}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, default=dict))
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
