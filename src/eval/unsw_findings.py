"""Map each UNSW triage finding to ground-truth categories via the hosts/ports it cites.

Approximate by design: broad findings (e.g. "web attacks on port 80") touch several categories.
Usage: python -m src.eval.unsw_findings
"""

import collections
import json
import re

from .unsw_score import ROOT, pcap_window, load_gt

RUNS = {  # pcap -> exported transcript (full-context condition)
    3: "triage-2026-09-26-05-35-27.txt", 1: "triage-2026-09-26-05-47-36.txt", 4: "triage-2026-09-26-06-02-02.txt",
    5: "triage-2026-09-26-06-35-34.txt", 10: "triage-2026-09-26-08-27-04.txt", 14: "triage-2026-09-26-08-38-24.txt"}
CATS = ["Analysis", "Backdoor", "DoS", "Exploits", "Fuzzers", "Generic", "Reconnaissance", "Shellcode", "Worms"]
KW = {r"\bTFTP\b": [69], r"(?<!T)\bFTP\b": [21], r"\bSMB|IPC\$|LSASS|MS08-067|NetBIOS|DCE/?RPC": [139, 445],
      r"portmap|RPC portmap|\bRPC\b": [111], r"\bSSH\b": [22], r"HTTP|web|IIS|SQLi|XSS": [80],
      r"SMTP|attachment": [25], r"Heartbleed|TLS": [443, 2444, 7002, 9090], r"MySQL": [3306], r"\bDNS\b": [53],
      r"SNMP": [161], r"IMAP": [143], r"POP3": [110]}
SKIP = re.compile(r"Actors|noise|Stale|false positive|Detection rules written|Suppression|Rothenburg|Other|"
                  r"3\.1 Confirmed|Decoder|Fragmentation|SNMP / DNS", re.I)


def final_report(text: str) -> str:
    i = text.rfind("\n## 1. ")
    return text[i:] if i >= 0 else ""


def analyse(transcript: str, pcap: int):
    """Returns (main categories Counter, touched categories Counter, covered GT indices, GT events)."""
    ev = load_gt(*pcap_window(pcap))
    rep = final_report((ROOT / transcript).read_text())
    main, touched, covered = collections.Counter(), collections.Counter(), set()
    for s in re.split(r"\n### ", rep)[1:]:
        head = s.split("\n")[0]
        if SKIP.search(head):
            continue
        body = s.split("\n## ")[0]
        victims = {"149.171.126." + m for m in re.findall(r"149\.171\.126\.(\d+)", body)} | \
                  {"149.171.126." + m for m in re.findall(r"`\.(\d{1,2})\b", body)}
        ports = {int(p) for p in re.findall(r"(?:149\.171\.126\.\d+|`?\.\d{1,2}):(\d+)", body)}
        for pat, ps in KW.items():
            if re.search(pat, head, re.I):
                ports |= set(ps)
        hits = [i for i, e in enumerate(ev) if e["dst"].startswith("149.171.126.")
                and (not victims or e["dst"] in victims) and ports and e["dport"].isdigit() and int(e["dport"]) in ports]
        covered.update(hits)
        c = collections.Counter(ev[i]["cat"] for i in hits)
        tot = sum(c.values())
        for cat, v in c.items():
            touched[cat] += 1
            if v / tot >= 0.10:
                main[cat] += 1
    return main, touched, covered, ev


def tcpudp_coverage(covered, ev):
    tcp, cov = collections.Counter(), collections.Counter()
    for i, e in enumerate(ev):
        if e["proto"] in ("tcp", "udp"):
            tcp[e["cat"]] += 1
            cov[e["cat"]] += i in covered
    return cov, tcp


def main():
    out = {n: analyse(f, n) for n, f in RUNS.items()}
    print("Y = main category of a finding (>=10% of its matched events); o = touched; . = none")
    print(f"{'':10}" + "".join(f"{c[:8]:>9}" for c in CATS))
    for n, (m, t, _, _) in out.items():
        print(f"unsw-{n:<5}" + "".join(f"{'Y' if m[c] else ('o' if t[c] else '.'):>9}" for c in CATS))
    tcp, cov = collections.Counter(), collections.Counter()
    for _, _, covered, ev in out.values():
        c, t = tcpudp_coverage(covered, ev)
        cov.update(c); tcp.update(t)
    print("\nGT events covered by the model's findings (TCP/UDP):")
    for c in CATS:
        print(f"  {c:<15}{cov[c]:>6} / {tcp[c]:<6} {100 * cov[c] / max(tcp[c], 1):5.1f}%")
    print(f"  {'TOTAL':<15}{sum(cov.values()):>6} / {sum(tcp.values()):<6} {100 * sum(cov.values()) / sum(tcp.values()):5.1f}%")
    json.dump({"categories": CATS,
               "runs": {f"unsw-{n}": {"main": [c for c in CATS if m[c]], "any": [c for c in CATS if t[c]]}
                        for n, (m, t, _, _) in out.items()},
               "coverage_tcpudp": {c: [cov[c], tcp[c]] for c in CATS}},
              open(ROOT / "docs/results/unsw_findings.json", "w"), indent=2)
    print("Saved docs/results/unsw_findings.json")


if __name__ == "__main__":
    main()
