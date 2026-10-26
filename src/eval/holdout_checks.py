"""Hold-out extras: AI-rule alerts on the benign-only captures (25, 50) and the combined genuine gain of all conditions.

Uses the frozen rule files (rules/snapshots/rounds_<cond>_holdout_frozen.rules) and the hold-out replays written by
`python -m src.eval.rounds --holdout --replay`. The combined figure is a union of per-condition genuine events, each
attributed within its own replay, so it is approximate.

Usage: python -m src.eval.holdout_checks    → docs/results/rounds.json["holdout_extra"]
"""

import json
import re
from pathlib import Path

from . import unsw_score as u
from .rounds import window_from

ROOT = Path(__file__).resolve().parents[2]
CLS = json.loads((ROOT / "docs/results/round_rule_classes.json").read_text())
CONDS = {"plain": "r2", "research": "r2", "hunt": "r1", "hunt2": "r1"}


def main():
    res = {"benign_captures": {}, "combined": {}, "combined_by_set": {}}
    union, per_cond = set(), {}
    tcp_total = 0
    for cond, rnd in CONDS.items():
        ai = {int(x) for x in re.findall(r"sid\s*:\s*(\d+)\s*;", (ROOT / f"rules/snapshots/rounds_{cond}_holdout_frozen.rules").read_text())}
        gen = {s for s in ai if CLS.get(str(s), {}).get("class") in ("signature", "behavioural")}
        fp = {}
        for n in ("25", "50"):
            al = u.load_alerts(ROOT / f"logs/unsw-{n}-{cond}-{rnd}-holdout/eve.json")
            fp[n] = sum(1 for a in al if a["sid"] in ai)
            fp[n + "_genuine"] = sum(1 for a in al if a["sid"] in gen)
        res["benign_captures"][cond] = fp
        mine = set()
        tcp_total = 0
        for n in ("1", "3", "6"):
            ev = u.load_gt(*window_from(ROOT / f"logs/unsw-{n}-baseline-holdout/eve.json"))
            idx = u.index_gt(ev)
            tcp = {i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")}
            tcp_total += len(tcp)
            al = u.load_alerts(ROOT / f"logs/unsw-{n}-{cond}-{rnd}-holdout/eve.json")
            odet, _ = u.match([a for a in al if a["sid"] not in ai], ev, idx, 2.0)
            gdet, _ = u.match([a for a in al if a["sid"] in gen], ev, idx, 2.0)
            mine |= {(n, i) for i in (gdet & tcp) - odet}
        per_cond[cond] = mine
        union |= mine
    note = "union of per-condition genuine events; each condition attributed within its own replay"
    res["combined"] = {"genuine_new_union": len(union), "tcpudp": tcp_total, "pts": round(100 * len(union) / tcp_total, 2), "note": note}
    for name, conds in (("plain+research+hunt", ("plain", "research", "hunt")), ("hunt+hunt2", ("hunt", "hunt2"))):
        un = set().union(*(per_cond[c] for c in conds))
        res["combined_by_set"][name] = {"genuine_new_union": len(un), "pts": round(100 * len(un) / tcp_total, 2)}
    rp = ROOT / "docs/results/rounds.json"
    r = json.loads(rp.read_text())
    r["holdout_extra"] = res
    rp.write_text(json.dumps(r, indent=2))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
