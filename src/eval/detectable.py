"""Detection measured against what a signature IDS could plausibly detect, not against every labelled event.

Two narrower denominators for UNSW-NB15 TCP/UDP attack events:
  content-detectable  the attacker sent application data in a matching flow (more TCP bytes than headers can
                      account for — 74 B per packet — or any UDP datagram). Conservative: tiny probes may be missed. Events without data — SYN probes, refused connections — can
                      only be caught by rate or topology logic, never by content.
  ever-detected       detected by at least one configuration we ran: baseline v2, the all-disabled-rules-enabled control
                      (dev only), or a genuine (signature/behavioural) AI rule of any round. A practical ceiling.

Usage: python -m src.eval.detectable    → docs/results/detectable.json
"""

import json
import re
from datetime import datetime
from pathlib import Path

from . import unsw_score as u
from .rounds import window_from

ROOT = Path(__file__).resolve().parents[2]
CLS = json.loads((ROOT / "docs/results/round_rule_classes.json").read_text())
GENUINE = ("signature", "behavioural")
CONDS = {"plain": "r2", "research": "r2", "hunt": "r1", "hunt2": "r1"}


def rule_sids(cond):
    return {int(x) for x in re.findall(r"sid\s*:\s*(\d+)\s*;", (ROOT / f"rules/snapshots/rounds_{cond}_holdout_frozen.rules").read_text())}


def payload_events(eve: Path, events, idx, tol=2.0):
    """Indices of events whose attacker side sent application data in a matching flow."""
    out = set()
    with open(eve) as fh:
        for line in fh:
            if '"event_type":"flow"' not in line:
                continue
            f = json.loads(line)
            proto = (f.get("proto") or "").lower()
            if proto not in ("tcp", "udp"):
                continue
            fs = datetime.fromisoformat(f["flow"]["start"]).timestamp()
            fe = datetime.fromisoformat(f["flow"]["end"]).timestamp()
            key = u.key_of(f["src_ip"], f.get("src_port", ""), f["dest_ip"], f.get("dest_port", ""), True)
            for i in idx.get(key, []):
                e = events[i]
                if fe < e["start"] - tol or fs > e["last"] + tol:
                    continue
                attacker_is_src = f["src_ip"] == e["src"]
                side = "toserver" if attacker_is_src else "toclient"
                pkts, byts = f["flow"][f"pkts_{side}"], f["flow"][f"bytes_{side}"]
                if proto == "udp":
                    sent = pkts > 0
                else:
                    # More bytes than headers alone can account for (74 B = Ethernet + IP + TCP with SYN options).
                    # The PSH flag is not usable: the traffic generator often sends data without it.
                    sent = byts > 74 * pkts
                if sent:
                    out.add(i)
    return out


def detected(eve: Path, events, idx, sids=None, exclude=None):
    al = u.load_alerts(eve)
    if sids is not None:
        al = [a for a in al if a["sid"] in sids]
    if exclude is not None:
        al = [a for a in al if a["sid"] not in exclude]
    return u.match(al, events, idx, 2.0)[0]


def score_set(captures, gt_window, base_log, cond_log, allon_log=None):
    res = {"tcpudp": 0, "content": 0, "ever": 0, "base": {"all": 0, "content": 0, "ever": 0}}
    gains = {c: {"all": 0, "content": 0} for c in CONDS}
    for n in captures:
        events = u.load_gt(*gt_window(n))
        idx = u.index_gt(events)
        tcp = {i for i, e in enumerate(events) if e["proto"] in ("tcp", "udp")}
        content = payload_events(base_log(n), events, idx) & tcp
        base = detected(base_log(n), events, idx) & tcp
        ever = set(base)
        if allon_log:
            ever |= detected(allon_log(n), events, idx) & tcp
        for cond, rnd in CONDS.items():
            ai = rule_sids(cond)
            gen = {s for s in ai if CLS.get(str(s), {}).get("class") in GENUINE}
            log = cond_log(n, cond, rnd)
            other = detected(log, events, idx, exclude=ai)
            mine = detected(log, events, idx, sids=gen) & tcp
            new = mine - other
            ever |= mine
            gains[cond]["all"] += len(new)
            gains[cond]["content"] += len(new & content)
        res["tcpudp"] += len(tcp); res["content"] += len(content); res["ever"] += len(ever)
        res["base"]["all"] += len(base); res["base"]["content"] += len(base & content); res["base"]["ever"] += len(base & ever)
    res["gains"] = gains
    return res


def main():
    dev = score_set([1, 3, 4, 5, 10, 14], u.pcap_window,
                    lambda n: ROOT / f"logs/unsw-{n}-baseline/eve.json",
                    lambda n, c, r: ROOT / f"logs/unsw-{n}-{c}-{r}/eve.json",
                    lambda n: ROOT / f"logs/unsw-{n}-allon/eve.json")
    hold = score_set(["1", "3", "6"], lambda n: window_from(ROOT / f"logs/unsw-{n}-baseline-holdout/eve.json"),
                     lambda n: ROOT / f"logs/unsw-{n}-baseline-holdout/eve.json",
                     lambda n, c, r: ROOT / f"logs/unsw-{n}-{c}-{r}-holdout/eve.json")
    out = {"dev": dev, "holdout": hold,
           "definitions": __doc__.split("Usage")[0].strip()}
    (ROOT / "docs/results/detectable.json").write_text(json.dumps(out, indent=2))
    for name, r in (("DEV (6 captures)", dev), ("HOLD-OUT (1, 3, 6)", hold)):
        print(f"== {name}: TCP/UDP {r['tcpudp']:,} | content-detectable {r['content']:,} ({100*r['content']/r['tcpudp']:.1f}%) | "
              f"ever-detected {r['ever']:,} ({100*r['ever']/r['tcpudp']:.1f}%)")
        b = r["base"]
        print(f"   baseline v2 detects: {100*b['all']/r['tcpudp']:.1f}% of all | {100*b['content']/r['content']:.1f}% of content-detectable | "
              f"{100*b['ever']/r['ever']:.1f}% of ever-detected")
        for c, g in r["gains"].items():
            print(f"   {c:8} genuine gain: +{g['all']} = +{100*g['all']/r['tcpudp']:.2f} pts of all | "
                  f"+{g['content']} = +{100*g['content']/r['content']:.2f} pts of content-detectable | "
                  f"+{100*g['all']/r['ever']:.2f} pts of ever-detected")


if __name__ == "__main__":
    main()
