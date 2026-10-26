"""Experiment 1: full sensor context vs alerts only, on UNSW-NB15 captures 1, 3 and 10.

Per condition: triage findings mapped to ground truth (unsw_findings.analyse), and the condition's own
rules replayed alone on top of the stock + CIC rule set, scored with the UNSW ground-truth matcher.

Usage: python -m src.eval.experiment1
"""

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from .unsw_findings import CATS, RUNS, analyse, final_report, tcpudp_coverage
from .unsw_score import ATTACKER_NET, index_gt, load_alerts, load_gt, match, pcap_window

ROOT = Path(__file__).resolve().parents[2]
PCAPS = [3, 1, 10]
FULL_SIDS = {7600201, 7600202, 7600203, 7600204, 7600205, 7601001, 7601002, 7601003}
OUT = ROOT / "docs/results/experiment1.json"


def header(transcript: Path) -> dict:
    h = transcript.read_text()[:1500]
    get = lambda k: (re.search(rf"^{k}:\s+(.+)$", h, re.M) or [None, ""])[1].strip()
    return {"file": transcript.name, "run": get("Run").split(" ")[0], "turns": int(get("Turns") or 0),
            "duration": get("Duration"), "status": "error" if "Status: error" in h else "completed"}


def bare_transcripts() -> dict:
    found = {}
    for f in sorted(ROOT.glob("triage-*.txt")):
        h = header(f)
        m = re.fullmatch(r"unsw-(\d+)-bare", h["run"])
        if m:
            found[int(m.group(1))] = f.name  # latest wins
    return found


OUTCOME = re.compile(r"[^.\n]*\b(success(ful(ly)?)?|succeeded|accepted|confirmed compromise|exfiltrat\w*|leak(ed)?|"
                     r"\d[\d,.]* ?(KB|MB|bytes|B)\b|cannot (be )?(confirm|determin|verif)\w*|unable to (confirm|determin|verif)\w*|"
                     r"not (be )?(confirm|verif)\w*|outcome (is )?unknown)[^.\n]*", re.I)
UNCONFIRMED = re.compile(r"cannot|unable|not (be )?(confirm|verif)|unknown", re.I)


def outcome_statements(transcript: str) -> tuple:
    """Sentences in the final report that assert or disclaim an attack outcome (success, data volume, leak)."""
    hits = [m.group(0) for m in OUTCOME.finditer(final_report((ROOT / transcript).read_text()))]
    return len(hits), sum(1 for h in hits if UNCONFIRMED.search(h))


def rule_statements(path: Path) -> list:
    stmts, cur = [], ""
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("#") and not cur:
            continue
        cur += line.rstrip("\\").rstrip() + " "
        if not line.rstrip().endswith("\\"):
            if cur.strip().startswith("alert"):
                stmts.append(cur.strip())
            cur = ""
    return stmts


def sid_of(stmt):
    return int(re.search(r"sid:(\d+);", stmt).group(1))


def replay(cond: str, rules: list) -> dict:
    rdir = ROOT / "rules/experiment1"
    rdir.mkdir(exist_ok=True)
    (rdir / f"{cond}.rules").write_text("\n".join(rules) + "\n")
    cfg = (ROOT / "config/unsw/v1.yaml").read_text().replace("generated/unsw/unsw_triage.rules", f"experiment1/{cond}.rules")
    cfg_path = ROOT / f"config/unsw/exp1-{cond}.yaml"
    cfg_path.write_text(cfg)
    loaded = {}
    for n in PCAPS:
        log = ROOT / f"logs/exp1-{cond}-unsw-{n}"
        log.mkdir(parents=True, exist_ok=True)
        (log / "eve.json").unlink(missing_ok=True)
        subprocess.run(["suricata", "-c", str(cfg_path), "--set", "threshold-file=", "-k", "none",
                        "-r", str(ROOT / f"data/pcaps/unsw/{n}.pcap"), "-l", str(log)],
                       capture_output=True, text=True, check=False)
        loaded[n] = re.search(r"(\d+) rules failed", (log / "suricata.log").read_text()).group(1)
    return loaded


def score(cond: str, sids: set) -> dict:
    res = {"base_detected": 0, "cond_detected": 0, "tcpudp_events": 0, "rules_fired": set(),
           "alerts": 0, "alerts_gt_matched": 0, "alerts_no_attacker": 0}
    for n in PCAPS:
        ev = load_gt(*pcap_window(n))
        idx = index_gt(ev)
        tcp = {i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")}
        base, _ = match(load_alerts(ROOT / f"logs/unsw-{n}-raw/eve.json"), ev, idx, 2.0)
        mine = [a for a in load_alerts(ROOT / f"logs/exp1-{cond}-unsw-{n}/eve.json") if a["sid"] in sids]
        det, per = match(mine, ev, idx, 2.0)
        res["base_detected"] += len(base & tcp)
        res["cond_detected"] += len((base | det) & tcp)
        res["tcpudp_events"] += len(tcp)
        for a, hit in zip(mine, per):
            res["alerts"] += 1
            res["rules_fired"].add(a["sid"])
            res["alerts_gt_matched"] += hit is not None
            res["alerts_no_attacker"] += not (a["src"].startswith(ATTACKER_NET) or a["dst"].startswith(ATTACKER_NET))
    res["rules_fired"] = sorted(res["rules_fired"])
    return res


def findings(transcripts: dict) -> dict:
    out = {}
    tot_cov, tot_tcp = Counter(), Counter()
    for n in PCAPS:
        main, touched, covered, ev = analyse(transcripts[n], n)
        cov, tcp = tcpudp_coverage(covered, ev)
        tot_cov.update(cov); tot_tcp.update(tcp)
        stated, unconfirmed = outcome_statements(transcripts[n])
        out[n] = {"main": [c for c in CATS if main[c]], "touched": [c for c in CATS if touched[c]],
                  "outcome_statements": stated, "outcome_unconfirmed": unconfirmed,
                  "covered_tcpudp": sum(cov.values()), "tcpudp": sum(tcp.values()), **header(ROOT / transcripts[n])}
    union = sorted({c for n in PCAPS for c in out[n]["main"]}, key=CATS.index)
    return {"per_run": out, "union_main": union,
            "covered_tcpudp": sum(tot_cov.values()), "tcpudp": sum(tot_tcp.values())}


def main():
    bare_tx = bare_transcripts()
    missing = [n for n in PCAPS if n not in bare_tx]
    assert not missing, f"no bare transcript for {missing}"
    full_rules = [s for s in rule_statements(ROOT / "rules/generated/unsw/unsw_triage.rules") if sid_of(s) in FULL_SIDS]
    bare_rules = rule_statements(ROOT / "rules/generated/unsw/unsw_bare.rules")
    result = {}
    for cond, tx, rules in (("full", {n: RUNS[n] for n in PCAPS}, full_rules), ("bare", bare_tx, bare_rules)):
        sids = {sid_of(s) for s in rules}
        failed = replay(cond, rules)
        result[cond] = {"findings": findings(tx), "rules_written": len(rules), "sids": sorted(sids),
                        "rules_failed_to_load_per_replay": failed, "replay": score(cond, sids)}
        f, r = result[cond]["findings"], result[cond]["replay"]
        print(f"\n== {cond.upper()}")
        for n in PCAPS:
            pr = f["per_run"][n]
            print(f"  unsw-{n}: {pr['status']}, {pr['turns']} turns, {pr['duration']}; main categories {pr['main']}; "
                  f"findings cover {pr['covered_tcpudp']}/{pr['tcpudp']} TCP/UDP events; outcome statements "
                  f"{pr['outcome_statements']} ({pr['outcome_unconfirmed']} 'cannot confirm')")
        print(f"  categories identified (union of main): {len(f['union_main'])} {f['union_main']}")
        print(f"  findings cover {f['covered_tcpudp']}/{f['tcpudp']} = {100 * f['covered_tcpudp'] / f['tcpudp']:.1f}%")
        print(f"  rules written {len(rules)}, fired {len(r['rules_fired'])} {r['rules_fired']}; failed to load per replay {failed}")
        print(f"  rule alerts {r['alerts']}, GT-matched {r['alerts_gt_matched']}, on non-attacker hosts {r['alerts_no_attacker']}")
        print(f"  TCP/UDP detection: stock+CIC {100 * r['base_detected'] / r['tcpudp_events']:.1f}% -> "
              f"with {cond} rules {100 * r['cond_detected'] / r['tcpudp_events']:.1f}%")
    OUT.write_text(json.dumps(result, indent=2, default=list))
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
