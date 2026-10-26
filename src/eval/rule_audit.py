"""Inventory of every AI-authored detection rule: provenance, load status, replay evidence, duplicates.

Provenance and status notes are established from the triage transcripts, git history and
Suricata logs; replay evidence is read from docs/results/{cic,unsw}_scores.json.

Usage: python -m src.eval.rule_audit
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/results/rule_audit.csv"

T = {
    "tue_v3": "DeepSeek V3, Tuesday triage (2 Sep; committed c14b002; no transcript kept)",
    "tue_claude": "Claude Opus 5, Tuesday triage (CLI run, not logged; committed c14b002)",
    "wed_v3": "DeepSeek V3, Wednesday tuned (triage-2026-09-04-04-10-26.txt)",
    "wed_v4": "DeepSeek V4 Pro, Wednesday raw (triage-2026-09-15-11-26-28.txt)",
    "thu_tuned": "DeepSeek V4 Pro, Thursday tuned (triage-2026-09-15-13-31-04.txt)",
    "thu_raw": "DeepSeek V4 Pro, Thursday raw (triage-2026-09-15-13-30-50.txt)",
    "fri_raw": "DeepSeek V4 Pro, Friday raw (triage-2026-09-15-13-30-09.txt)",
    "fri_tuned": "DeepSeek V4 Pro, Friday tuned (triage-2026-09-15-13-30-21.txt)",
    "fri_demo": "DeepSeek V4 Pro, Friday validation run for Week 9 demo (21 Sep; no transcript kept)",
}

# sid -> (dataset, provenance key or text, status note, duplicate_of)
RULES = {
    **{s: ("CIC", "tue_v3", "", "") for s in range(9000001, 9000006)},
    **{s: ("CIC", "tue_v3", "did not fire on Tuesday replay (stateful hostbits chain / thresholds never met)", "") for s in (9000001, 9000002, 9000003, 9000005)},
    9500001: ("CIC", "tue_claude", "", ""),
    9500002: ("CIC", "tue_claude", "", ""),
    3000001: ("CIC", "wed_v3", "deleted by V4 Pro on a false 'stock ET' claim; text preserved in transcript", ""),
    3000002: ("CIC", "wed_v3", "deleted by V4 Pro on a false 'stock ET' claim; text preserved in transcript", ""),
    3000003: ("CIC", "wed_v3", "rewritten in place by V4 Pro (http.method -> raw TCP depth:8)", ""),
    3000004: ("CIC", "wed_v4", "", ""),
    7600101: ("CIC", "wed_v4", "loads but can never fire: tls.invalid_encrypted_heartbeat not registered in Suricata 8.0.6", ""),
    7600102: ("CIC", "wed_v4", "Heartbleed file never loaded in any Wednesday replay", ""),
    7600103: ("CIC", "wed_v4", "Heartbleed file never loaded in any Wednesday replay", ""),
    7600001: ("CIC", "thu_tuned", "", ""),
    7600002: ("CIC", "thu_tuned", "fails to parse: smb.command keyword unknown", ""),
    7600003: ("CIC", "thu_tuned", "", ""),
    7600004: ("CIC", "thu_tuned", "false positive: fires on routine FTP uploads from every workstation, Tuesday and Thursday; all label-matched hits are BENIGN", ""),
    7600005: ("CIC", "thu_tuned", "fails to parse: smb.command keyword unknown", ""),
    7600006: ("CIC", "thu_tuned", "fails to parse: malformed dcerpc.iface", ""),
    7600007: ("CIC", "thu_raw", "fires only on compromised host .8; labels mark these flows BENIGN (CIC labels only 36 Infiltration flows) - disputed", ""),
    9500003: ("CIC", "fri_tuned", "", ""),
    9600001: ("CIC", "fri_raw", "", ""),
    9600002: ("CIC", "fri_raw", "", ""),
    9600003: ("CIC", "fri_raw", "copy placed in Claude's bruteforce_campaigns.rules so it would load", "9600001"),
    9600004: ("CIC", "fri_raw", "copy placed in Claude's bruteforce_campaigns.rules so it would load", "9600002"),
    9600005: ("CIC", "fri_demo", "first ARES draft; file never loaded; superseded by 9700001-3", ""),
    9600006: ("CIC", "fri_demo", "first ARES draft; file never loaded; superseded by 9700001-3", ""),
    9600007: ("CIC", "fri_demo", "first ARES draft; file never loaded; superseded by 9700001-3", ""),
    9700001: ("CIC", "fri_demo", "defined in two files (friday_botnet_c2.rules, bruteforce_campaigns.rules)", ""),
    9700002: ("CIC", "fri_demo", "defined in two files (friday_botnet_c2.rules, bruteforce_campaigns.rules)", ""),
    9700003: ("CIC", "fri_demo", "defined in two files (friday_botnet_c2.rules, bruteforce_campaigns.rules)", ""),
    7600201: ("UNSW", "unsw-3", "", ""),
    7600202: ("UNSW", "unsw-3", "", ""),
    7600203: ("UNSW", "unsw-3", "", ""),
    7600204: ("UNSW", "unsw-1", "", ""),
    7600205: ("UNSW", "unsw-1", "", ""),
    7600401: ("UNSW", "unsw-4", "", ""),
    7600402: ("UNSW", "unsw-4", "", ""),
    7600501: ("UNSW", "unsw-5", "re-authored copy of CIC rule", "7600102"),
    7600502: ("UNSW", "unsw-5", "re-authored copy of CIC rule", "7600103"),
    7600503: ("UNSW", "unsw-5", "", ""),
    7600504: ("UNSW", "unsw-5", "", ""),
    7600505: ("UNSW", "unsw-5", "", ""),
    7601001: ("UNSW", "unsw-10", "model skipped validation; replay-validated by the team", ""),
    7601002: ("UNSW", "unsw-10", "model skipped validation; replay-validated by the team", ""),
    7601003: ("UNSW", "unsw-10", "model skipped validation; replay-validated by the team", ""),
    7601401: ("UNSW", "unsw-14", "duplicate logic", "7601002"),
    7601402: ("UNSW", "unsw-14", "duplicate logic", "7600505"),
    7601403: ("UNSW", "unsw-14", "same purpose as 7601003 but broader (13 vs 1 hits on pcap 14)", ""),
}
UNSW_PROV = "DeepSeek V4 Pro, UNSW-NB15 {} triage"
BROKEN = {7600002, 7600005, 7600006}
DEAD = {7600101}
DELETED = {3000001, 3000002}
SUPERSEDED = {9600005, 9600006, 9600007}


def rule_files() -> dict:
    files = {}
    for f in (ROOT / "rules/generated").rglob("*.rules"):
        for sid in re.findall(r"sid:(\d+);", f.read_text()):
            files.setdefault(int(sid), set()).add(f.name)
    return files


def main():
    cic = json.loads((ROOT / "docs/results/cic_scores.json").read_text())["ai_rules"]
    unsw = json.loads((ROOT / "docs/results/unsw_scores.json").read_text())["ai_rules"]
    files = rule_files()
    rows = []
    for sid, (ds, prov, note, dup) in sorted(RULES.items()):
        c, u = cic.get(str(sid)), unsw.get(str(sid))
        if sid in BROKEN:
            load = "fails to load"
        elif sid in DEAD:
            load = "loads, cannot fire"
        elif sid in DELETED:
            load = "deleted"
        else:
            load = "loads"
        rows.append({
            "sid": sid, "dataset": ds,
            "author_session": T.get(prov) or UNSW_PROV.format(prov),
            "file": ", ".join(sorted(files.get(sid, []))) or "(removed)",
            "load_status": load,
            "cic_alerts": c["alerts"] if c else "", "cic_on_attack": c["attack"] if c else "",
            "cic_on_benign": c["benign"] if c else "",
            "unsw_alerts": u["alerts"] if u else "", "unsw_gt_matched": u["matched"] if u else "",
            "unsw_attacker_involved": u["attacker_involved"] if u else "",
            "unsw_pcaps_fired": len(u["pcaps_fired"]) if u else "",
            "duplicate_of": dup, "notes": note,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    for ds in ("CIC", "UNSW"):
        rs = [r for r in rows if r["dataset"] == ds]
        fired = [r for r in rs if (r["cic_alerts"] if ds == "CIC" else r["unsw_alerts"])]
        print(f"== {ds}: {len(rs)} authored")
        print(f"   load status: {dict(Counter(r['load_status'] for r in rs))}")
        print(f"   duplicates/copies: {sum(1 for r in rs if r['duplicate_of'])}, "
              f"superseded drafts: {sum(1 for r in rs if r['sid'] in SUPERSEDED)}")
        print(f"   fired in replay on own dataset: {len(fired)}")
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
