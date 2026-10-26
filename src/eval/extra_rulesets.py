"""Do additional open rulesets raise detection, and do AI-authored rules still add value on top?

Layers: ET Open -> ET Open + each extra ruleset -> ET Open + all extra -> + AI-authored rules.
Scored with the same ground-truth matchers as unsw_score (UNSW-NB15) and cic_score (CIC Tue/Thu).
Rulesets were chosen from the observed traffic profile (services under attack), not from the labels.

Usage: python -m src.eval.extra_rulesets
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import cic_score, unsw_score

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/results/extra_rulesets.json"
EXTRA = {"Snort Community": "snort_community", "Stamus lateral": "stamus_lateral",
         "Nmap scans": "nmap_scans", "PT Open": "pt_open"}
ENABLED = {"ET disabled (selected)": "et_disabled_selected", "Snort disabled (selected)": "snort_disabled_selected"}
UNSW_PCAPS = unsw_score.PCAPS
CIC_DAYS = {"Tuesday": "tuesday", "Thursday": "thursday"}


def sids_in(path: Path) -> set:
    out = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"\s*(alert|drop|reject|pass)\b", line):
            m = re.search(r"\bsid\s*:\s*(\d+)", line)
            if m:
                out.add(int(m.group(1)))
    return out


def ruleset_map() -> dict:
    owner = {}
    for name, stem in {**EXTRA, **ENABLED}.items():
        for s in sids_in(ROOT / f"rules/extra/{stem}.rules"):
            owner[s] = name
    for s in unsw_score.custom_sids():
        owner[s] = "AI"
    return owner  # anything else is ET Open (incl. Suricata engine events)


def layers():
    """(name, rule sets counted, log suffix)."""
    base = [("ET Open", {"ET Open"}, "extra")]
    base += [(f"ET Open + {n}", {"ET Open", n}, "extra") for n in EXTRA]
    base += [("ET Open + all extra", {"ET Open", *EXTRA}, "extra"),
             ("ET Open + all extra + AI", {"ET Open", *EXTRA, "AI"}, "extra-ai")]
    base += [(f"all extra + {n}", {"ET Open", *EXTRA, n}, "plus") for n in ENABLED]
    base += [("all extra + re-enabled", {"ET Open", *EXTRA, *ENABLED}, "plus"),
             ("all extra + re-enabled + AI", {"ET Open", *EXTRA, *ENABLED, "AI"}, "plus-ai")]
    return base


def unsw(owner):
    res = {name: {"detected": Counter(), "alerts": 0, "no_attacker": 0} for name, _, _ in layers()}
    tot = Counter()
    per_set = defaultdict(lambda: {"alerts": 0, "gt_matched": 0, "no_attacker": 0})
    for n in UNSW_PCAPS:
        ev = unsw_score.load_gt(*unsw_score.pcap_window(n))
        idx = unsw_score.index_gt(ev)
        tcp = [i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")]
        for i in tcp:
            tot[ev[i]["cat"]] += 1
        logs = {sfx: unsw_score.load_alerts(ROOT / f"logs/unsw-{n}-{sfx}/eve.json") for sfx in ("extra", "extra-ai", "plus", "plus-ai")}
        extra = logs["plus"]
        for name, sets, sfx in layers():
            src = logs[sfx]
            alerts = [a for a in src if owner.get(a["sid"], "ET Open") in sets]
            det, per = unsw_score.match(alerts, ev, idx, 2.0)
            for i in det:
                if ev[i]["proto"] in ("tcp", "udp"):
                    res[name]["detected"][ev[i]["cat"]] += 1
            res[name]["alerts"] += len(alerts)
            res[name]["no_attacker"] += sum(1 for a in alerts if not (a["src"].startswith(unsw_score.ATTACKER_NET)
                                                                        or a["dst"].startswith(unsw_score.ATTACKER_NET)))
        _, per = unsw_score.match(extra, ev, idx, 2.0)
        for a, hit in zip(extra, per):
            rs = owner.get(a["sid"], "ET Open")
            if rs in EXTRA or rs in ENABLED:
                p = per_set[rs]
                p["alerts"] += 1
                p["gt_matched"] += hit is not None
                p["no_attacker"] += not (a["src"].startswith(unsw_score.ATTACKER_NET) or a["dst"].startswith(unsw_score.ATTACKER_NET))
    return res, tot, dict(per_set)


def cic(owner):
    out = {}
    for day, stem in CIC_DAYS.items():
        cfg = cic_score.DAYS[day]
        flows = cic_score.load_flows(cfg["labels"])
        idx = defaultdict(list)
        for i, f in enumerate(flows):
            idx[cic_score.key_of(f[0], f[1], f[2], f[3], f[4])].append(i)
        totals = Counter(f[7] for f in flows)
        logs = {sfx: list(cic_score.iter_alerts(f"{stem}-{sfx}")) for sfx in ("extra", "extra-ai", "plus", "plus-ai")}
        day_res = {}
        for name, sets, sfx in layers():
            src = logs[sfx]
            det, lab = set(), Counter()
            for a in src:
                rs = owner.get(a["sid"], "ET Open")
                if rs not in sets or cic_score.is_engine_event(a["sid"]):
                    continue
                hits = cic_score.match_alert(a, flows, idx, 120.0)
                det.update(hits)
                lab["unmatched" if not hits else ("attack" if any(flows[i][7] != "BENIGN" for i in hits) else "benign")] += 1
            day_res[name] = {"detected": Counter(flows[i][7] for i in det), "alerts": lab}
        out[day] = {"flows": totals, "layers": day_res}
    return out


def main():
    owner = ruleset_map()
    u_res, u_tot, per_set = unsw(owner)
    total = sum(u_tot.values())
    print(f"== UNSW-NB15 (6 captures), TCP/UDP ground-truth events: {total}")
    print(f"{'layer':<30}{'detected':>10}{'recall':>8}{'alerts':>9}{'no-attacker':>13}")
    for name, _, _ in layers():
        r = u_res[name]
        d = sum(r["detected"].values())
        print(f"{name:<30}{d:>10}{100 * d / total:>7.1f}%{r['alerts']:>9}{r['no_attacker']:>13}")
    print("\nper category (ET Open | + all extra | + re-enabled | + re-enabled + AI):")
    for c in sorted(u_tot):
        v = [100 * u_res[l]["detected"][c] / u_tot[c] for l in ("ET Open", "ET Open + all extra", "all extra + re-enabled", "all extra + re-enabled + AI")]
        print(f"  {c:<15}{u_tot[c]:>6}  " + "  ".join(f"{x:5.1f}%" for x in v))
    print("\nper extra ruleset (UNSW alerts / GT-matched / on non-attacker hosts):")
    for k, v in per_set.items():
        print(f"  {k:<16}{v['alerts']:>7}{v['gt_matched']:>8}{v['no_attacker']:>8}")

    c_res = cic(owner)
    for day, r in c_res.items():
        print(f"\n== CIC-IDS2017 {day}")
        attacks = [l for l in r["flows"] if l != "BENIGN"]
        for name, _, _ in layers():
            L = r["layers"][name]
            prec = L["alerts"]["attack"] / max(1, L["alerts"]["attack"] + L["alerts"]["benign"])
            cats = sum(1 for l in attacks if L["detected"][l] > 0)
            print(f"  {name:<30} categories {cats}/{len(attacks)}  precision {100 * prec:5.1f}%  " +
                  "  ".join(f"{l[:14]} {100 * L['detected'][l] / r['flows'][l]:.1f}%" for l in attacks))
    OUT.write_text(json.dumps({"unsw": {"tcpudp_events": u_tot, "layers": u_res, "per_extra_ruleset": per_set},
                               "cic": c_res}, indent=2, default=dict))
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
