"""Figures for the final report and deck added in October: UNSW baseline v2, AI rounds, the hunt condition.

Every figure is written twice into docs/figures/: an .svg (deck, web) and a 300-dpi .png (Word).
Charts use matplotlib; diagrams are hand-written SVG rendered with cairosvg. Numbers come from
docs/results/*.json, rule files and run logs — none are typed in here.

Usage: venv/bin/python -m src.eval.make_figures_v2
"""

import json
import re
from collections import Counter
from pathlib import Path

import cairosvg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs/results"
FIG = ROOT / "docs/figures"

# Same palette as make_figures.py, plus status colours.
STOCK, AI, MODEL = "#9aa3ad", "#1f4e79", "#d9822b"
BAD, GOOD, INK, MUTED, PAPER = "#b03a2e", "#2e7d4f", "#1d2733", "#5b6774", "#f4f6f8"
STEEL_ = "#4f6d8a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "svg.fonttype": "none"})

CONDS = [("plain", "Plain triage"), ("research", "Research tool"), ("hunt", "Hunt (engineer workflow)"), ("hunt2", "Hunt2 (+ keyword tool)")]


def load(name):
    return json.loads((RES / name).read_text())


def save(fig, stem):
    fig.savefig(FIG / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_svg(svg, stem):
    (FIG / f"{stem}.svg").write_text(svg)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(FIG / f"{stem}.png"), scale=3.0, background_color="white")


def sids(path):
    return [int(s) for s in re.findall(r"^alert.*?\bsid\s*:\s*(\d+)", path.read_text(), re.M)] if path.exists() else []


# ------------------------------------------------------------------ charts

def fig_baseline_ladder():
    u = load("extra_rulesets.json")["unsw"]
    total = sum(u["tcpudp_events"].values())
    steps = [("ET Open\nas shipped", "ET Open"),
             ("+ Snort Community,\nStamus, PT Open, Nmap", "ET Open + all extra"),
             ("+ disabled ET\nfamilies (selected)", "all extra + ET disabled (selected)"),
             ("+ disabled Snort\nfamilies (selected)", "all extra + Snort disabled (selected)"),
             ("Baseline v2\n(all selected families)", "all extra + re-enabled")]
    vals = [100 * sum(u["layers"][k]["detected"].values()) / total for _, k in steps]
    alerts = [u["layers"][k]["alerts"] for _, k in steps]
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    cols = [STOCK] * 4 + [AI]
    bars = ax.bar(range(len(steps)), vals, color=cols, width=0.62)
    for i, (b, v, a) in enumerate(zip(bars, vals, alerts)):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f}%", ha="center", fontsize=10, fontweight="bold", color=INK)
        ax.text(b.get_x() + b.get_width() / 2, 1.0, f"{a:,}\nalerts", ha="center", fontsize=7.5, color="white")
    ax.set_xticks(range(len(steps)), [s for s, _ in steps], fontsize=8)
    ax.set_ylabel("UNSW-NB15 TCP/UDP attack events detected (%)")
    ax.set_ylim(0, max(vals) * 1.22)
    ax.set_title(f"Strengthening the human baseline (6 dev captures, {total:,} TCP/UDP attack events)", fontsize=11, loc="left")
    ax.annotate("extra rulesets add\nalmost nothing", xy=(1, vals[1] + 2), xytext=(1.1, vals[4] * 0.85), fontsize=8,
                color=MUTED, ha="center", arrowprops=dict(arrowstyle="->", color=MUTED))
    save(fig, "fig4-4_baseline_ladder")


def fig_baseline_control():
    d = load("baseline_control.json")
    rows = [("Baseline v2\n(families chosen from\ntraffic profile)", d["baseline"], AI),
            ("Control: every\ndisabled rule\nenabled", d["allon"], BAD)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 3.4))
    for ax, key, label, fmt in ((a1, "det", "TCP/UDP attack events detected (%)", "{:.1f}%"),
                                (a2, "no_attacker", "Alerts on hosts that are not attackers", "{:,}")):
        vals = [100 * r[1]["det"] / r[1]["tcpudp"] if key == "det" else r[1][key] for r in rows]
        bars = ax.bar(range(2), vals, color=[r[2] for r in rows], width=0.55)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v * 1.02, fmt.format(v), ha="center", fontsize=10, fontweight="bold")
        ax.set_xticks(range(2), [r[0] for r in rows], fontsize=8)
        ax.set_title(label, fontsize=9.5, loc="left")
        ax.set_ylim(0, max(vals) * 1.2)
    ratio = d["allon"]["no_attacker"] / d["baseline"]["no_attacker"]
    fig.suptitle(f"Selecting rule families by service: +{100 * (d['allon']['det'] - d['baseline']['det']) / d['baseline']['tcpudp']:.1f} pts "
                 f"detection forgone for {ratio:.0f}x less noise", fontsize=11, x=0.02, ha="left")
    fig.tight_layout()
    save(fig, "fig4-5_baseline_control")


def fig_category_ceiling():
    d = load("baseline_control.json")["baseline"]
    tot, det = d["tcpudp_by_cat"], d["detected_by_cat"]
    cats = sorted(tot, key=lambda c: tot[c])
    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    y = range(len(cats))
    ax.barh(y, [tot[c] for c in cats], color="#dfe3e8", height=0.6, label="Attack events (TCP/UDP)")
    ax.barh(y, [det.get(c, 0) for c in cats], color=AI, height=0.6, label="Detected by baseline v2")
    for i, c in enumerate(cats):
        ax.text(tot[c] + 40, i, f"{100 * det.get(c, 0) / tot[c]:.0f}%  ({det.get(c, 0):,}/{tot[c]:,})", va="center", fontsize=8)
    ax.set_yticks(list(y), cats)
    ax.set_xlim(0, max(tot.values()) * 1.35)
    ax.set_xlabel("Events")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    ax.set_title("Where the misses are: baseline v2 detection by UNSW-NB15 attack category", fontsize=11, loc="left")
    save(fig, "fig4-6_category_ceiling")


def fig_rounds_attribution():
    r = load("rounds.json")
    keys = [("plain-r1", "Plain R1"), ("plain-r2", "Plain R2"), ("research-r1", "Research R1"),
            ("research-r2", "Research R2"), ("hunt-r1", "Hunt R1*"), ("hunt2-r1", "Hunt2 R1")]
    keys = [(k, l) for k, l in keys if k in r]
    tot = r[keys[0][0]]["tcpudp"]
    old = [100 * (r[k]["full_det"] - r[k]["base_det"]) / tot for k, _ in keys]
    attr = [100 * r[k]["ai_new"] / tot for k, _ in keys]
    gen = [100 * r[k]["ai_new_genuine"] / tot for k, _ in keys]
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    x = range(len(keys)); w = 0.27
    b0 = ax.bar([i - w for i in x], old, w, color="#dfe3e8", label="Old metric: fresh replay vs stored baseline")
    b1 = ax.bar(list(x), attr, w, color=MODEL, label="Attributable: events only AI-rule alerts catch")
    b2 = ax.bar([i + w for i in x], gen, w, color=AI, label="Genuine: attributable, topology rules removed")
    for bars in (b0, b1, b2):
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, v + 0.15, f"+{v:.2f}" if v < 1 else f"+{v:.1f}", ha="center", fontsize=7, rotation=90 if v < 1 else 0, va="bottom")
    ax.set_xticks(list(x), [l for _, l in keys])
    ax.set_ylabel(f"Gain in TCP/UDP detection (pts of {tot:,} events)")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("AI rounds on baseline v2: plain and research gains were topology; hunt's were genuine", fontsize=11, loc="left")
    ax.text(0, -0.2, "*Hunt rules written on capture 3 before the reasoning-carry fix, on captures 1 and 10 after it (Section V). Scored on all 6 dev captures.",
            transform=ax.transAxes, fontsize=7.5, color=MUTED)
    save(fig, "fig5-7_rounds_attribution")


def fig_rule_classes():
    cls = load("round_rule_classes.json")
    order = [("signature", AI), ("behavioural", "#4f86b8"), ("topology", BAD), ("dataset-indicator", MODEL)]
    data = []
    for c, label in CONDS:
        cnt = Counter(cls.get(str(s), {}).get("class", "unclassified") for s in sids(ROOT / f"rules/generated/unsw/rounds_{c}.rules"))
        data.append((label, cnt))
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    for i, (label, cnt) in enumerate(data):
        left = 0
        for name, col in order:
            n = cnt.get(name, 0)
            if n:
                ax.barh(i, n, left=left, color=col, height=0.55)
                ax.text(left + n / 2, i, str(n), ha="center", va="center", color="white", fontsize=9, fontweight="bold")
                left += n
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in order]
    ax.legend(handles, [n for n, _ in order], frameon=False, fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.set_yticks(range(len(data)), [d[0] for d in data])
    ax.invert_yaxis()
    ax.set_xlabel("AI-authored rules (both rounds)")
    ax.set_title("What kind of rule did each condition write?", fontsize=11, loc="left")
    save(fig, "fig5-8_rule_classes")


def fig_gate_coverage():
    rows = load("test_rule_gate.json")["protocol_records_by_source_role_capture3"]
    protos = sorted(rows, key=lambda p: -(rows[p]["internal_client"] + rows[p]["external"]))
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    x = range(len(protos)); w = 0.38
    ax.bar([i - w / 2 for i in x], [rows[p]["internal_client"] for p in protos], w, color=GOOD, label="Internal clients (known-good)")
    ax.bar([i + w / 2 for i in x], [rows[p]["external"] for p in protos], w, color=STOCK, label="External hosts")
    ax.set_yscale("symlog", linthresh=10)
    for i, p in enumerate(protos):
        ok = rows[p]["internal_client"] > 0
        ax.text(i, max(rows[p]["internal_client"], rows[p]["external"]) * 1.6, "testable" if ok else "blind",
                ha="center", fontsize=8, fontweight="bold", color=GOOD if ok else BAD)
    ax.set_xticks(list(x), [p.upper() for p in protos])
    ax.set_ylabel("Protocol records, capture 3 (log scale)")
    ax.set_ylim(0, 2e5)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("The anti-topology gate can only test protocols that internal hosts also use", fontsize=11, loc="left")
    save(fig, "fig5-9_gate_coverage")


def fig_hunt_transfer():
    hunt = sids(ROOT / "rules/generated/unsw/rounds_hunt.rules")
    caps = [1, 3, 4, 5, 10, 14]
    src = lambda s: 3 if s <= 7800007 else 1 if s <= 7800016 else 10   # order the rule file was written in
    grid = {}
    for n in caps:
        c = Counter()
        p = ROOT / f"logs/unsw-{n}-hunt-r1/eve.json"
        if p.exists():
            for line in open(p):
                if '"event_type":"alert"' in line:
                    s_ = json.loads(line)["alert"]["signature_id"]
                    if s_ in hunt:
                        c[s_] += 1
        grid[n] = c
    names = {}
    for line in (ROOT / "rules/generated/unsw/rounds_hunt.rules").read_text().splitlines():
        m = re.search(r'msg:"([^"]+)".*sid:(\d+)', line)
        if m:
            names[int(m.group(2))] = m.group(1).replace("EXPLOIT ", "").replace("SERVER-WEBAPP ", "")[:44]
    groups = [(3, "written on capture 3 — before the fix"), (1, "written on capture 1 — after the fix"),
              (10, "written on capture 10 — after the fix")]
    rows = []
    for g, label in groups:
        rows.append(("hdr", label, g))
        rows += [("rule", s_, g) for s_ in hunt if src(s_) == g]
    fig, ax = plt.subplots(figsize=(8.2, 0.27 * len(rows) + 0.9))
    for i, (kind, val, g) in enumerate(rows):
        if kind == "hdr":
            ax.text(-0.1, i + 0.55, val, ha="right", va="center", fontsize=8.5, fontweight="bold",
                    color=BAD if g == 3 else GOOD)
            continue
        for j, n in enumerate(caps):
            v = grid[n][val]
            home = n == g
            col = (AI if not home else STOCK) if v else "#eef1f4"
            ax.add_patch(plt.Rectangle((j, i + 0.05), 0.92, 0.85, color=col))
            ax.text(j + 0.46, i + 0.48, str(v), ha="center", va="center", fontsize=7.5, color="white" if v else MUTED)
        ax.text(-0.1, i + 0.48, f"{val}  {names.get(val, '')}", ha="right", va="center", fontsize=7)
    ax.set_xlim(0, len(caps)); ax.set_ylim(len(rows), 0)
    ax.set_xticks([j + 0.46 for j in range(len(caps))], [f"capture {n}" for n in caps], fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("Hunt rules: alerts on each development capture (grey = the capture the rule was written on)",
                 fontsize=10.5, loc="left", pad=22)
    save(fig, "fig5-10_hunt_transfer")


def fig_generalisation():
    r, un = load("rounds.json"), load("rounds_unseen_dev.json")
    conds = [("plain", "r2", "Plain R2"), ("research", "r2", "Research R2"), ("hunt", "r1", "Hunt R1"), ("hunt2", "r1", "Hunt2 R1")]
    sets = [("All 6 dev captures", lambda c, k: 100 * r[k]["ai_new_genuine"] / r[k]["tcpudp"], "#c9d6e3"),
            ("Dev captures 4, 5, 14\n(no rules written there)", lambda c, k: un[k]["pts"], "#7fa7c9"),
            ("Hold-out, 22 Jan\n(never seen)", lambda c, k: 100 * r[k + "-holdout"]["ai_new_genuine"] / r[k + "-holdout"]["tcpudp"], AI)]
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    w = 0.26
    nc = len(conds)
    for si, (lab, f, col) in enumerate(sets):
        vals = [f(c, f"{c}-{rd}") for c, rd, _ in conds]
        bars = ax.bar([i + (si - 1) * w for i in range(nc)], vals, w, color=col, label=lab)
        for b_, v in zip(bars, vals):
            ax.text(b_.get_x() + b_.get_width() / 2, v + 0.03, f"+{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(range(nc), [l for _, _, l in conds])
    ax.set_ylabel("Genuine detection gain (percentage points)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Genuine gain holds on traffic the rules were not written on", fontsize=11, loc="left")
    ax.text(0, -0.17, "Signature and behavioural rules only; events no other alert in the same replay detected. "
            "Hunt captures 1, 10 and all hunt2 runs had the reasoning-carry fix; plain and research did not.",
            transform=ax.transAxes, fontsize=7.2, color=MUTED)
    save(fig, "fig5-12_generalisation")


def fig_holdout():
    r = load("rounds.json")
    if "baseline-holdout" not in r:
        return
    dev = load("baseline_control.json")["baseline"]
    h = r["baseline-holdout"]
    vals = [100 * dev["det"] / dev["tcpudp"], 100 * h["base_det"] / h["tcpudp"]]
    prec = [100 * dev["matching"] / dev["alerts"], 100 * h["base_gt"] / h["base_alerts"]]
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    x = range(2); w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], vals, w, color=AI, label="TCP/UDP attack events detected")
    b2 = ax.bar([i + w / 2 for i in x], prec, w, color=STOCK, label="Alerts that match an attack event")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.1f}%", ha="center", fontsize=9)
    ax.set_xticks(list(x), [f"Dev set (17 Feb, 6 captures)\n{dev['tcpudp']:,} events",
                            f"Hold-out (22 Jan, 3 captures)\n{h['tcpudp']:,} events"], fontsize=8.5)
    ax.set_ylim(0, 100); ax.set_ylabel("%")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("Frozen baseline v2 on unseen traffic", fontsize=11, loc="left")
    save(fig, "fig5-11_holdout_baseline")


# ------------------------------------------------------------------ diagrams (hand-written SVG)

def _box(x, y, w, h, title, lines=(), fill="#ffffff", stroke=AI, title_col=None, size=13):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
           f'<text x="{x + w / 2}" y="{y + 26}" text-anchor="middle" font-size="{size}" font-weight="700" fill="{title_col or INK}">{title}</text>']
    for i, l in enumerate(lines):
        out.append(f'<text x="{x + w / 2}" y="{y + 48 + 17 * i}" text-anchor="middle" font-size="11" fill="{MUTED}">{l}</text>')
    return "\n".join(out)


def _arrow(x1, y1, x2, y2, col=MUTED, label=None, dash=False):
    d = ' stroke-dasharray="6 4"' if dash else ""
    s = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2"{d} marker-end="url(#ah)"/>'
    if label:
        s += f'<text x="{(x1 + x2) / 2 + 6}" y="{(y1 + y2) / 2 - 6}" font-size="11" fill="{col}">{label}</text>'
    return s


def _svg(w, h, body, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="DejaVu Sans, Arial, sans-serif">
<title>{title}</title>
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker></defs>
<rect width="{w}" height="{h}" fill="white"/>
{body}
</svg>'''


def fig_hunt_workflow():
    W, H = 1100, 560
    steps = [("1  Coverage map", ["event types vs alerts", "per app protocol"]),
             ("2  Hunt the gaps", ["stack_values: rare", "content fields first"]),
             ("3  Hypothesis", ["search_rules: covered?", "lookup_vulnerability"]),
             ("4  Write rule", ["ADS comment: goal,", "blind spots, FPs"]),
             ("5  test_rule", ["replay as written", "+ widened to any"])]
    body = [f'<text x="40" y="44" font-size="22" font-weight="700" fill="{INK}">Hunt condition: the detection-engineering lifecycle as an agent procedure</text>',
            f'<text x="40" y="70" font-size="13" fill="{MUTED}">Profile unsw-v2-hunt · no attacker range in the prompt · every rule must pass the gate before the engine lets it be saved</text>']
    bw, gap, y = 180, 25, 120
    for i, (t, ls) in enumerate(steps):
        x = 40 + i * (bw + gap)
        body.append(_box(x, y, bw, 90, t, ls, fill="#eef4fa" if i < 4 else "#fff6ec", stroke=AI if i < 4 else MODEL))
        if i < 4:
            body.append(_arrow(x + bw, y + 45, x + bw + gap - 2, y + 45))
    gx = 40 + 4 * (bw + gap) + bw / 2
    body.append(_arrow(gx, y + 90, gx, 300))
    body.append(f'<polygon points="{gx},300 {gx + 95},350 {gx},400 {gx - 95},350" fill="#ffffff" stroke="{MODEL}" stroke-width="2"/>')
    body.append(f'<text x="{gx}" y="346" text-anchor="middle" font-size="13" font-weight="700" fill="{INK}">VERDICT</text>')
    body.append(f'<text x="{gx}" y="364" text-anchor="middle" font-size="10.5" fill="{MUTED}">per sid</text>')
    body.append(_arrow(gx, 400, gx, 450, col=GOOD, label="PASS"))
    body.append(_box(gx - 110, 452, 220, 80, "6  append_to_file", ["only the exact text", "that passed"], fill="#edf7f0", stroke=GOOD))
    body.append(f'<path d="M {gx - 95} 350 L 520 350 L 520 210" fill="none" stroke="{BAD}" stroke-width="2" marker-end="url(#ah)"/>')
    body.append(f'<text x="540" y="378" font-size="12" fill="{BAD}" font-weight="700">FAIL → tighten on content/behaviour, or drop</text>')
    body.append(f'<text x="540" y="396" font-size="11" fill="{MUTED}">fires 0 times · or widened rule fires between internal hosts</text>')
    body.append(_box(40, 270, 380, 150, "Engine-enforced write gate", [
        "write_file to the rule file: blocked", "any path except the profile rule file: blocked",
        "a rule edited after its test: blocked", "untested rule: blocked"], fill=PAPER, stroke=STOCK, size=13))
    body.append(f'<text x="40" y="470" font-size="12" fill="{MUTED}">Sources of the procedure: Palantir ADS framework; SpecterOps capability abstraction;</text>')
    body.append(f'<text x="40" y="488" font-size="12" fill="{MUTED}">stack counting (least frequency of occurrence); RuleAutoPilot execution-grounded validation.</text>')
    save_svg(_svg(W, H, "\n".join(body), "Hunt workflow"), "fig3-6_hunt_workflow")


def fig_test_rule_gate():
    g = load("test_rule_gate.json")["examples"]
    W, H = 1100, 470
    body = [f'<text x="40" y="44" font-size="22" font-weight="700" fill="{INK}">test_rule: is the rule detecting behaviour, or just the source address?</text>',
            f'<text x="40" y="70" font-size="13" fill="{MUTED}">Two replays of capture 3 (~20 s): the rule as written, and the same rule widened to any any -&gt; any any. Internal-to-internal traffic is known-good.</text>']
    for i, ex in enumerate(g):
        y = 100 + i * 180
        col = BAD if ex["verdict"] == "FAIL" else GOOD
        body.append(f'<rect x="40" y="{y}" width="1020" height="160" rx="12" fill="{PAPER}" stroke="{col}" stroke-width="2"/>')
        body.append(f'<text x="64" y="{y + 32}" font-size="14" font-weight="700" fill="{INK}">{ex["kind"].capitalize()} example</text>')
        body.append(f'<text x="64" y="{y + 56}" font-size="12" font-family="DejaVu Sans Mono, monospace" fill="{INK}">{ex["rule"].replace("<", "&lt;").replace(">", "&gt;")}</text>')
        mx = max(ex["widened"]["ext->int"] + ex["widened"]["int->int"], 1)
        for j, (lab, d) in enumerate((("as written", ex["as_written"]), ("widened", ex["widened"]))):
            yy = y + 80 + j * 32
            body.append(f'<text x="64" y="{yy + 15}" font-size="12" fill="{MUTED}">{lab}</text>')
            w1 = 560 * d["ext->int"] / mx; w2 = 560 * d["int->int"] / mx
            body.append(f'<rect x="170" y="{yy}" width="{max(w1, 2)}" height="20" fill="{STOCK}"/>')
            body.append(f'<rect x="{170 + w1}" y="{yy}" width="{w2}" height="20" fill="{BAD}"/>')
            body.append(f'<text x="{180 + w1 + w2}" y="{yy + 15}" font-size="12" fill="{INK}">{d["ext->int"]:,} external→internal · {d["int->int"]:,} internal→internal</text>')
        body.append(f'<rect x="900" y="{y + 20}" width="130" height="44" rx="8" fill="{col}"/>')
        body.append(f'<text x="965" y="{y + 49}" text-anchor="middle" font-size="18" font-weight="700" fill="white">{ex["verdict"]}</text>')
    save_svg(_svg(W, H, "\n".join(body), "test_rule gate"), "fig3-7_test_rule_gate")


def fig_profiles():
    from src.profiles import PROFILES
    W, H = 1100, 520
    body = [f'<text x="40" y="44" font-size="22" font-weight="700" fill="{INK}">Experiment profiles: one named bundle per condition</text>',
            f'<text x="40" y="70" font-size="13" fill="{MUTED}">The UI, CLI and batch runner select a profile; the engine takes everything else from it. Scored profiles are frozen.</text>']
    names = [n for n in PROFILES if n != "unsw"]
    bw, y0 = 196, 100
    for i, n in enumerate(names):
        p = PROFILES[n]
        x = 40 + i * (bw + 12)
        hunt = n.endswith("hunt")
        short = {"search_rules": "search", "lookup_vulnerability": "NVD", "stack_values": "stack", "test_rule": "test_rule"}
        tools = "8 + " + ", ".join(short[t] for t in p.get("extra_tools", ())) if p.get("extra_tools") else "base 8 tools"
        lines = [p["suricata_config"].split("/")[-1], (p.get("rule_file") or "").split("/")[-1] or ("alerts only" if p.get("alerts_only") else "triage prompt")]
        body.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="250" rx="10" fill="{"#fff6ec" if hunt else "#eef4fa"}" stroke="{MODEL if hunt else AI}" stroke-width="2"/>')
        body.append(f'<text x="{x + bw / 2}" y="{y0 + 28}" text-anchor="middle" font-size="14" font-weight="700" fill="{INK}">{n}</text>')
        body.append(f'<text x="{x + bw / 2}" y="{y0 + 48}" text-anchor="middle" font-size="11" fill="{MUTED}">dataset: {p["dataset"]}</text>')
        rows = [("config", lines[0]), ("prompt", "hunt procedure" if hunt else ("bare alerts" if p.get("alerts_only") else "triage")),
                ("tools", tools[:30]), ("", tools[30:60]), ("gate", "test_rule required" if p.get("require_test") else "—"),
                ("attacker range", "hidden" if hunt else ("shown" if p["dataset"] == "unsw" else "n/a"))]
        for j, (k, v) in enumerate(rows):
            yy = y0 + 80 + 26 * j
            if k:
                body.append(f'<text x="{x + 12}" y="{yy}" font-size="10.5" fill="{MUTED}">{k}</text>')
            body.append(f'<text x="{x + bw - 12}" y="{yy}" text-anchor="end" font-size="10.5" fill="{INK}">{v}</text>')
    body.append(_box(300, 400, 500, 90, "src/profiles.py  →  engine.run_triage(profile)",
                     ["system prompt · task message · tool set · Suricata config · blocked files · log allowlist"],
                     fill=PAPER, stroke=STOCK, size=13))
    for i in range(len(names)):
        x = 40 + i * (bw + 12) + bw / 2
        body.append(f'<line x1="{x}" y1="{y0 + 250}" x2="{550}" y2="400" stroke="{STOCK}" stroke-width="1.2"/>')
    save_svg(_svg(W, H, "\n".join(body), "Experiment profiles"), "fig3-5_experiment_profiles")


def fig_detectability():
    d = load("detectable.json")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), sharey=False)
    for ax, (key, title) in zip(axes, (("dev", "Development (6 captures)"), ("holdout", "Hold-out (captures 1, 3, 6)"))):
        r = d[key]
        bars = [("All TCP/UDP\nattack events", r["tcpudp"], r["base"]["all"]),
                ("Content-detectable\n(attacker sent data)", r["content"], r["base"]["content"]),
                ("Ever-detected\n(any configuration)", r["ever"], r["base"]["ever"])]
        x = range(len(bars))
        ax.bar(x, [b[1] for b in bars], color="#dfe3e8", width=0.62, label="Events in the set")
        ax.bar(x, [b[2] for b in bars], color=AI, width=0.62, label="Detected by baseline v2")
        for i, (lab, tot, det) in enumerate(bars):
            ax.text(i, tot * 1.02, f"{100 * det / tot:.1f}%", ha="center", fontsize=9, fontweight="bold", color=INK)
        ax.set_xticks(list(x), [b[0] for b in bars], fontsize=7.5)
        ax.set_title(title, fontsize=10, loc="left")
        ax.set_ylim(0, r["tcpudp"] * 1.15)
        g = r["gains"]
        ax.text(0, -0.27, "Genuine AI gain, pts of ever-detected:\n" + "   ".join(
            f"{c} +{100 * g[c]['all'] / r['ever']:.2f}" for c in ("plain", "research", "hunt", "hunt2")),
                transform=ax.transAxes, fontsize=8, color=INK, va="top")
    axes[0].set_ylabel("Attack events")
    axes[0].legend(frameon=False, fontsize=8, loc="center left")
    fig.suptitle("Most missed attacks carried data: the gap is missing signatures, not undetectable traffic",
                 fontsize=11, x=0.01, ha="left")
    fig.subplots_adjust(bottom=0.27, top=0.84, wspace=0.22, left=0.07, right=0.99)
    save(fig, "fig5-13_detectability")


def fig_hunt_overlap():
    import json as _j
    from . import unsw_score as u
    cls = load("round_rule_classes.json")
    sets = {}
    top = {}
    for c in ("hunt", "hunt2"):
        txt = (ROOT / f"rules/generated/unsw/rounds_{c}.rules").read_text()
        names = {int(m.group(2)): m.group(1) for m in re.finditer(r'msg:"([^"]+)".*?sid:(\d+)', txt)}
        gen = {s_ for s_ in names if cls.get(str(s_), {}).get("class") in ("signature", "behavioural")}
        evs, per = set(), Counter()
        for n in (1, 3, 4, 5, 10, 14):
            ev = u.load_gt(*u.pcap_window(n)); idx = u.index_gt(ev)
            tcp = {i for i, e in enumerate(ev) if e["proto"] in ("tcp", "udp")}
            al = u.load_alerts(ROOT / f"logs/unsw-{n}-{c}-r1/eve.json")
            odet, _ = u.match([a for a in al if a["sid"] not in names], ev, idx, 2.0)
            for s_ in gen:
                d_, _ = u.match([a for a in al if a["sid"] == s_], ev, idx, 2.0)
                new = (d_ & tcp) - odet
                per[s_] += len(new)
                evs |= {(n, i) for i in new}
        sets[c] = evs
        top[c] = [(names[s_].replace("SERVER-WEBAPP ", "").replace("WEB-ATTACK ", "").replace("WEB ", "")[:38], k)
                  for s_, k in per.most_common(4)]
    both = len(sets["hunt"] & sets["hunt2"]); h_only = len(sets["hunt"] - sets["hunt2"]); h2_only = len(sets["hunt2"] - sets["hunt"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.4, 3.4), gridspec_kw={"width_ratios": [1, 1.5]})
    a1.barh([1], [h_only], color=AI, height=0.5); a1.barh([1], [both], left=[h_only], color="#7fa7c9", height=0.5)
    a1.barh([0], [both], left=[h_only], color="#7fa7c9", height=0.5); a1.barh([0], [h2_only], left=[h_only + both], color=MODEL, height=0.5)
    a1.text(h_only / 2, 1, f"{h_only}\nhunt only", ha="center", va="center", color="white", fontsize=8)
    a1.text(h_only + both / 2, 0.5, f"{both} found by both", ha="center", va="center", fontsize=8.5, fontweight="bold")
    a1.text(h_only + both + h2_only / 2, 0, f"{h2_only}\nhunt2 only", ha="center", va="center", color="white", fontsize=8)
    a1.set_yticks([0, 1], ["Hunt2", "Hunt"]); a1.set_xlabel("Genuine attack events added (dev)")
    a1.set_title("Two runs of the same workflow find different attacks", fontsize=10, loc="left")
    a2.axis("off")
    y = 0.95
    for c, col, lab in (("hunt", AI, "Hunt — top rules"), ("hunt2", MODEL, "Hunt2 — top rules")):
        a2.text(0, y, lab, fontsize=9.5, fontweight="bold", color=col, transform=a2.transAxes); y -= 0.09
        for nm, k in top[c]:
            a2.text(0.02, y, f"+{k:<4} {nm}", fontsize=8.5, family="DejaVu Sans Mono", transform=a2.transAxes); y -= 0.085
        y -= 0.05
    save(fig, "fig5-14_hunt_overlap")


def fig_limits():
    W, H = 1100, 600
    groups = [
        ("Tooling gap — fixed in hunt2", MODEL, ["Guessed keywords: smb.filename (absent), tls.subject",
                                                 "Fell back to raw-byte regexes", "Fix: suricata_keywords tool → 0 failed loads"]),
        ("Rule-language limit", BAD, ["DNS high-entropy names (DGA, tunnelling)",
                                      "Needs a statistic over the name",
                                      "Possible with Suricata's lua keyword"]),
        ("Our design choices", STEEL_, ["POP3/IMAP/SMTP spam and fuzz sessions",
                                        "Only separable by rate or source: no IP pivot,",
                                        "and the gate cannot test POP3/SIP/SMB"]),
        ("Correct judgement", GOOD, ["SNMP probing already covered by deployed rules",
                                     "Lab-specific LDAP string dropped (hunt)",
                                     "Over-narrow single-character SMB rule dropped"]),
    ]
    body = [f'<text x="40" y="44" font-size="22" font-weight="700" fill="{INK}">Why the agent did not write a rule</text>',
            f'<text x="40" y="70" font-size="13" fill="{MUTED}">Activity the hunt reports flagged as attack-like but left without a rule, grouped by cause</text>']
    bw, bh = 500, 230
    for i, (title, col, lines) in enumerate(groups):
        x = 40 + (i % 2) * (bw + 20); y = 100 + (i // 2) * (bh + 20)
        body.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="12" fill="{PAPER}" stroke="{col}" stroke-width="2.5"/>')
        body.append(f'<rect x="{x}" y="{y}" width="{bw}" height="46" rx="12" fill="{col}"/>')
        body.append(f'<rect x="{x}" y="{y + 30}" width="{bw}" height="16" fill="{col}"/>')
        body.append(f'<text x="{x + 20}" y="{y + 30}" font-size="16" font-weight="700" fill="white">{title}</text>')
        for j, l in enumerate(lines):
            body.append(f'<text x="{x + 24}" y="{y + 86 + 42 * j}" font-size="14" fill="{INK}">• {l}</text>')
    save_svg(_svg(W, H, "\n".join(body), "Agent limits"), "fig5-15_agent_limits")


def fig_agent_tools():
    W, H = 1100, 640
    groups = [
        ("Investigate", AI, [("count_alerts", "alerts per signature"), ("count_by", "count any field"),
                             ("query_eve_json", "jq query, capped"), ("read_file", "+ list_directory: allowlisted")]),
        ("Hunt", "#4f86b8", [("stack_values", "rarest values first"), ("", "hunt, hunt2 only")]),
        ("Research", MODEL, [("search_rules", "already covered?"), ("lookup_vulnerability", "local NVD copy"),
                             ("suricata_keywords", "valid keywords (hunt2)")]),
        ("Validate", GOOD, [("run_suricata", "replay with the rules"), ("test_rule", "anti-topology gate"),
                            ("", "(hunt, hunt2)")]),
        ("Write", BAD, [("write_file", "rules/generated/ only"), ("append_to_file", "suppressions need"),
                        ("", "human approval")]),
    ]
    body = [f'<text x="40" y="44" font-size="22" font-weight="700" fill="{INK}">The agent&#8217;s toolkit: what DeepSeek can do, and only that</text>',
            f'<text x="40" y="70" font-size="13" fill="{MUTED}">The model only proposes a tool call (JSON); the engine checks it and runs it. 13 tools, selected per experiment profile.</text>']
    body.append(_box(420, 95, 260, 74, "DeepSeek V4 Pro / Claude", ["proposes the next tool call"], fill=PAPER, stroke=STOCK))
    body.append(_box(400, 205, 300, 84, "Triage engine (src/engine.py)", ["validates paths, applies the profile,", "runs the tool, returns the result"], fill="#eef4fa", stroke=AI))
    body.append(_arrow(550, 169, 550, 203)); body.append(_arrow(530, 205, 530, 171))
    xs = [40, 250, 460, 670, 880]
    for (title, col, lines), x in zip(groups, xs):
        y = 330
        body.append(f'<rect x="{x}" y="{y}" width="190" height="192" rx="10" fill="white" stroke="{col}" stroke-width="2.2"/>')
        body.append(f'<rect x="{x}" y="{y}" width="190" height="34" rx="10" fill="{col}"/><rect x="{x}" y="{y + 20}" width="190" height="14" fill="{col}"/>')
        body.append(f'<text x="{x + 95}" y="{y + 22}" text-anchor="middle" font-size="13" font-weight="700" fill="white">{title}</text>')
        yy = y + 56
        for name, desc in lines:
            if name:
                body.append(f'<text x="{x + 12}" y="{yy}" font-size="11.5" font-weight="700" font-family="DejaVu Sans Mono, monospace" fill="{INK}">{name}</text>')
                yy += 15
            body.append(f'<text x="{x + 12}" y="{yy}" font-size="10.5" fill="{MUTED}">{desc}</text>')
            yy += 19
        body.append(f'<line x1="{550}" y1="289" x2="{x + 95}" y2="{y}" stroke="{STOCK}" stroke-width="1.2"/>')
    body.append(f'<rect x="40" y="535" width="1030" height="80" rx="10" fill="{PAPER}" stroke="{STOCK}" stroke-width="1.5"/>')
    body.append(f'<text x="60" y="562" font-size="13" font-weight="700" fill="{INK}">Engine-enforced safeguards</text>')
    body.append(f'<text x="60" y="584" font-size="11.5" fill="{MUTED}">Read allowlist (logs/, config/, rules/, data/pcaps/) — labels, notes, transcripts refused · per-profile blocked files and log allowlist ·</text>')
    body.append(f'<text x="60" y="603" font-size="11.5" fill="{MUTED}">suppressions need human approval · hunt profiles: append-only and only rules that passed test_rule unchanged · output caps and timeouts</text>')
    save_svg(_svg(W, H, "\n".join(body), "Agent tools"), "fig3-8_agent_tools")


def main():
    FIG.mkdir(exist_ok=True)
    for f in (fig_baseline_ladder, fig_baseline_control, fig_category_ceiling, fig_rounds_attribution, fig_rule_classes,
              fig_gate_coverage, fig_hunt_transfer, fig_generalisation, fig_detectability, fig_hunt_overlap, fig_limits, fig_holdout, fig_hunt_workflow, fig_test_rule_gate, fig_profiles, fig_agent_tools):
        f()
        print("ok", f.__name__)


if __name__ == "__main__":
    main()
