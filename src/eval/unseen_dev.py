"""Genuine AI-rule gain on the development captures no condition wrote rules on (4, 5, 14).

Rules are written on captures 3, 1 and 10, so those captures flatter every condition. Captures 4, 5 and 14 were replayed
and scored but never shown to the model; they are the fairest within-dev test of whether rules transfer.

Usage: python -m src.eval.unseen_dev    → docs/results/rounds_unseen_dev.json
"""

import json
import re
from pathlib import Path

from . import unsw_score as u

ROOT = Path(__file__).resolve().parents[2]
CLS = json.loads((ROOT / "docs/results/round_rule_classes.json").read_text())
CONDS = {"plain": "r2", "research": "r2", "hunt": "r1", "hunt2": "r1"}
UNSEEN = (4, 5, 14)


def main():
    out = {}
    for cond, rnd in CONDS.items():
        ai = {int(x) for x in re.findall(r"sid\s*:\s*(\d+)\s*;", (ROOT / f"rules/generated/unsw/rounds_{cond}.rules").read_text())}
        gen = {s for s in ai if CLS.get(str(s), {}).get("class") in ("signature", "behavioural")}
        tot = new = 0
        for n in UNSEEN:
            ev = u.load_gt(*u.pcap_window(n))
            idx = u.index_gt(ev)
            tcp = {i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")}
            tot += len(tcp)
            al = u.load_alerts(ROOT / f"logs/unsw-{n}-{cond}-{rnd}/eve.json")
            odet, _ = u.match([a for a in al if a["sid"] not in ai], ev, idx, 2.0)
            gdet, _ = u.match([a for a in al if a["sid"] in gen], ev, idx, 2.0)
            new += len((gdet & tcp) - odet)
        out[f"{cond}-{rnd}"] = {"captures": list(UNSEEN), "tcpudp": tot, "genuine_new": new, "pts": round(100 * new / tot, 2)}
        print(f"{cond}-{rnd}: genuine new on captures 4/5/14: +{new} of {tot} (+{100 * new / tot:.2f} pts)")
    (ROOT / "docs/results/rounds_unseen_dev.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
