"""AI rounds on the UNSW-NB15 baseline v2: plain vs research-tool condition.

For each condition, replays every capture with config/unsw/baseline-<cond>.yaml (baseline v2 + that condition's
AI rules as they stand now) and scores against ground truth. Rules are written on captures 3, 1 and 10; the other
captures (and the hold-out day, when given) measure transfer. Transcripts are read to count research lookups and
to tag rules written after a lookup.

Usage: python -m src.eval.rounds --round 1 [--replay] [--pcaps 1 3 4 5 10 14] [--holdout] [--conds hunt]
"""

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from . import unsw_score

ROOT = Path(__file__).resolve().parents[2]
CONDS = ("plain", "research", "hunt", "hunt2")
OUT = ROOT / "docs/results/rounds.json"
CLASSES = ROOT / "docs/results/round_rule_classes.json"
GENUINE = ("signature", "behavioural")  # topology and dataset-indicator rules are not genuine gain


def rule_sids(path: Path) -> set:
    return {int(m) for m in re.findall(r"sid:\s*(\d+)\s*;", path.read_text())} if path.exists() else set()


def transcripts(cond: str) -> list:
    out = []
    for f in sorted(ROOT.glob("triage-*.txt")):
        head = f.read_text()[:1200]
        # Match the whole profile name: "unsw-v2-hunt" must not match "unsw-v2-hunt2".
        if re.search(rf"^(Dataset|Profile): +unsw-v2-{re.escape(cond)}\b(?!\d)", head, re.M):
            out.append(f)
    return out


def research_usage(cond: str) -> dict:
    """Lookups made, and SIDs first written after the run's first lookup."""
    lookups, after, searches = 0, set(), 0
    for f in transcripts(cond):
        text = f.read_text()
        first = text.find("[TOOL CALL] lookup_vulnerability")
        lookups += text.count("[TOOL CALL] lookup_vulnerability")
        searches += text.count("[TOOL CALL] search_rules")
        for m in re.finditer(r"\[TOOL CALL\] (write_file|append_to_file)\n(\{.*?\n\})", text, re.S):
            if first >= 0 and m.start() > first:
                after |= {int(x) for x in re.findall(r"sid:\s*(\d+)\s*;", m.group(2))}
    return {"runs": len(transcripts(cond)), "lookups": lookups, "search_rules_calls": searches, "sids_after_lookup": sorted(after)}


def replay(cond: str, rnd: int, pcaps, tag: str):
    for n in pcaps:
        pcap = f"data/pcaps/unsw/{n}.pcap" if isinstance(n, int) else f"data/pcaps/unsw/day1/{n}"
        run = f"unsw-{n}-{cond}-r{rnd}{tag}".replace(".pcap", "")
        subprocess.run([str(ROOT / "scripts/run_suricata.sh"), "unsw", f"baseline-{cond}", pcap, run], check=True)


def replay_baseline(pcaps, tag: str):
    """Hold-out only: replay the frozen baseline v2 (no AI rules) into logs/unsw-<n>-baseline-holdout/."""
    for n in pcaps:
        name = str(n).replace(".pcap", "")
        subprocess.run([str(ROOT / "scripts/run_suricata.sh"), "unsw", "baseline", f"data/pcaps/unsw/day1/{n}",
                        f"unsw-{name}-baseline{tag}"], check=True)


def score_baseline(pcaps, tag: str) -> dict:
    res = Counter()
    for n in pcaps:
        name = str(n).replace(".pcap", "")
        base_log = ROOT / f"logs/unsw-{name}-baseline{tag}/eve.json"
        lo, hi = window_from(base_log)
        ev = unsw_score.load_gt(lo, hi)
        idx = unsw_score.index_gt(ev)
        tcp = {i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")}
        base = unsw_score.load_alerts(base_log)
        bdet, bper = unsw_score.match(base, ev, idx, 2.0)
        print(f"   {n}: window {lo:.0f}-{hi:.0f} ({(hi - lo) / 60:.1f} min), GT events {len(ev)} (TCP/UDP {len(tcp)}), "
              f"alerts {len(base)}, detected TCP/UDP {len(bdet & tcp)}")
        res["gt_events"] += len(ev)
        res["tcpudp"] += len(tcp)
        res["base_det"] += len(bdet & tcp)
        res["base_alerts"] += len(base)
        res["base_gt"] += sum(h is not None for h in bper)
    return dict(res)


def score(cond: str, rnd: int, pcaps, tag: str, ai_sids: set) -> dict:
    """full_det - base_det compares a fresh replay with the stored baseline log, so replay variance
    (thresholds are not deterministic) counts as gain. ai_new is the attributable figure: TCP/UDP events
    matched by the AI rules' alerts and by no other alert in the same replay (CLAUDE.md §3.10)."""
    classes = json.loads(CLASSES.read_text()) if CLASSES.exists() else {}
    genuine = {s for s in ai_sids if classes.get(str(s), {}).get("class") in GENUINE}
    res = Counter()
    res["unclassified_rules"] = len({s for s in ai_sids if str(s) not in classes})
    for n in pcaps:
        name = str(n).replace(".pcap", "")
        base_log = ROOT / f"logs/unsw-{name}-baseline{tag}/eve.json"  # hold-out: its own baseline replay
        run_log = ROOT / f"logs/unsw-{name}-{cond}-r{rnd}{tag}/eve.json"
        ev = unsw_score.load_gt(*unsw_score.pcap_window(n)) if isinstance(n, int) else unsw_score.load_gt(*window_from(base_log))
        idx = unsw_score.index_gt(ev)
        tcp = {i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")}
        base = unsw_score.load_alerts(base_log)
        full = unsw_score.load_alerts(run_log)
        mine = [a for a in full if a["sid"] in ai_sids]
        bdet, bper = unsw_score.match(base, ev, idx, 2.0)
        fdet, fper = unsw_score.match(full, ev, idx, 2.0)
        mdet, mper = unsw_score.match(mine, ev, idx, 2.0)
        gdet, _ = unsw_score.match([a for a in mine if a["sid"] in genuine], ev, idx, 2.0)
        odet, _ = unsw_score.match([a for a in full if a["sid"] not in ai_sids], ev, idx, 2.0)
        res["ai_new"] += len((mdet & tcp) - odet)
        res["ai_new_genuine"] += len((gdet & tcp) - odet)
        res["tcpudp"] += len(tcp)
        res["base_det"] += len(bdet & tcp)
        res["full_det"] += len(fdet & tcp)
        res["base_alerts"] += len(base)
        res["base_gt"] += sum(h is not None for h in bper)
        res["full_alerts"] += len(full)
        res["full_gt"] += sum(h is not None for h in fper)
        res["ai_alerts"] += len(mine)
        res["ai_gt"] += sum(h is not None for h in mper)
        res["ai_noattacker"] += sum(1 for a in mine if not (a["src"].startswith(unsw_score.ATTACKER_NET) or a["dst"].startswith(unsw_score.ATTACKER_NET)))
    return dict(res)


def window_from(eve: Path):
    lo, hi = float("inf"), 0.0
    with open(eve) as fh:
        for line in fh:
            ev = json.loads(line)
            if ev.get("event_type") == "stats":
                continue
            from datetime import datetime
            t = datetime.fromisoformat(ev["timestamp"]).timestamp()
            lo, hi = min(lo, t), max(hi, t)
    return lo, hi


def fired(cond: str, rnd: int, pcaps, tag: str, ai_sids: set) -> set:
    out = set()
    for n in pcaps:
        name = str(n).replace(".pcap", "")
        for a in unsw_score.load_alerts(ROOT / f"logs/unsw-{name}-{cond}-r{rnd}{tag}/eve.json"):
            if a["sid"] in ai_sids:
                out.add(a["sid"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--pcaps", nargs="*", default=[1, 3, 4, 5, 10, 14])
    ap.add_argument("--holdout", action="store_true", help="score the day-1 hold-out pcaps in data/pcaps/unsw/day1/")
    ap.add_argument("--conds", nargs="*", choices=CONDS, default=list(CONDS))
    ap.add_argument("--baseline-only", action="store_true",
                    help="with --holdout: replay and score only the frozen baseline v2 (no AI rules)")
    args = ap.parse_args()
    pcaps = sorted(p.name for p in (ROOT / "data/pcaps/unsw/day1").glob("*.pcap")) if args.holdout else [int(p) for p in args.pcaps]
    tag = "-holdout" if args.holdout else ""
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    if args.holdout and (args.replay or args.baseline_only):
        if args.replay:
            replay_baseline(pcaps, tag)
        r = score_baseline(pcaps, tag)
        results["baseline-holdout"] = r
        print(f"== baseline v2 on hold-out: TCP/UDP detection {100 * r['base_det'] / max(1, r['tcpudp']):.1f}% "
              f"({r['base_det']}/{r['tcpudp']}); alerts matching an attack {100 * r['base_gt'] / max(1, r['base_alerts']):.1f}%")
        if args.baseline_only:
            OUT.write_text(json.dumps(results, indent=2))
            print(f"Saved {OUT.relative_to(ROOT)}")
            return
    for cond in args.conds:
        sids = rule_sids(ROOT / f"rules/generated/unsw/rounds_{cond}.rules")
        if args.replay:
            replay(cond, args.round, pcaps, tag)
        r = score(cond, args.round, pcaps, tag, sids)
        fset = fired(cond, args.round, pcaps, tag, sids)
        use = research_usage(cond)
        key = f"{cond}-r{args.round}{tag}"
        results[key] = {**r, "rules_written": len(sids), "rules_fired": len(fset), "usage": use,
                        "fired_after_lookup": len(fset & set(use["sids_after_lookup"]))}
        pct = lambda a, b: 100 * a / max(1, b)
        print(f"== {key}: rules written {len(sids)}, fired {len(fset)}; research lookups {use['lookups']}, "
              f"search_rules calls {use['search_rules_calls']}; rules written after a lookup that fired: {results[key]['fired_after_lookup']}")
        print(f"   attributable to AI rules: +{r['ai_new']} TCP/UDP events (+{pct(r['ai_new'], r['tcpudp']):.2f} pts); "
              f"genuine (signature/behavioural) +{r['ai_new_genuine']} (+{pct(r['ai_new_genuine'], r['tcpudp']):.2f} pts)"
              + (f"; {r['unclassified_rules']} rule(s) not yet classified" if r['unclassified_rules'] else ""))
        print(f"   [replay-vs-stored, includes replay variance] baseline {pct(r['base_det'], r['tcpudp']):.1f}% -> "
              f"{pct(r['full_det'], r['tcpudp']):.1f}% (+{r['full_det'] - r['base_det']} events)")
        print(f"   alerts matching an attack: baseline {pct(r['base_gt'], r['base_alerts']):.1f}% -> {pct(r['full_gt'], r['full_alerts']):.1f}%;"
              f"   AI-rule alerts {r['ai_alerts']} ({pct(r['ai_gt'], r['ai_alerts']):.1f}% matching), on normal hosts {r['ai_noattacker']}")
    OUT.write_text(json.dumps(results, indent=2))
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
