"""Render report figures from docs/results/*.json into docs/figures/.

Usage: venv/bin/python -m src.eval.make_figures
"""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs/results"
FIG = ROOT / "docs/figures"

STOCK, AI, MODEL = "#9aa3ad", "#1f4e79", "#d9822b"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 200, "savefig.bbox": "tight"})


def load(name):
    return json.loads((RES / name).read_text())


def bar_labels(ax, bars, fmt="{:.1f}%", pad=0.6):
    for b in bars:
        w = b.get_width()
        ax.text(w + pad, b.get_y() + b.get_height() / 2, fmt.format(w), va="center", fontsize=8)


def fig_cic_recall():
    d = load("cic_scores.json")["days"]
    rows = []
    for day in ("Tuesday", "Wednesday", "Thursday", "Friday"):
        for lab, n in d[day]["flows"].items():
            if lab == "BENIGN":
                continue
            rows.append((f"{lab} ({day[:3]})", n, d[day]["detected_stock"].get(lab, 0), d[day]["detected_stock_ai"].get(lab, 0)))
    rows.sort(key=lambda r: r[3] / r[1])
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    y = range(len(rows))
    h = 0.38
    b1 = ax.barh([i + h / 2 for i in y], [100 * r[2] / r[1] for r in rows], h, color=STOCK, label="Stock ET Open")
    b2 = ax.barh([i - h / 2 for i in y], [100 * r[3] / r[1] for r in rows], h, color=AI, label="Stock + AI-authored rules")
    bar_labels(ax, b1); bar_labels(ax, b2)
    ax.set_yticks(list(y), [f"{r[0]}  n={r[1]:,}" for r in rows], fontsize=8)
    ax.set_xlabel("Labelled attack flows with at least one matching alert (%)")
    ax.set_xlim(0, 80)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("CIC-IDS2017: flow-level detection by attack label", fontsize=11, loc="left")
    fig.savefig(FIG / "fig5-1_cic_recall.png"); plt.close(fig)


def fig_unsw_recall():
    d = load("unsw_scores.json")
    tot, st, ai = d["gt_events_tcpudp"], d["detected_tcpudp"]["stock"], d["detected_tcpudp"]["stock+cic+unsw"]
    cats = sorted(tot, key=lambda c: ai.get(c, 0) / tot[c])
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    y = range(len(cats))
    h = 0.38
    b1 = ax.barh([i + h / 2 for i in y], [100 * st.get(c, 0) / tot[c] for c in cats], h, color=STOCK, label="Stock ET Open")
    b2 = ax.barh([i - h / 2 for i in y], [100 * ai.get(c, 0) / tot[c] for c in cats], h, color=AI, label="Stock + AI-authored rules")
    bar_labels(ax, b1); bar_labels(ax, b2)
    ax.set_yticks(list(y), [f"{c}  n={tot[c]:,}" for c in cats], fontsize=8)
    ax.set_xlabel("TCP/UDP ground-truth attack events with at least one matching alert (%)")
    ax.set_xlim(0, 45)
    s_all = 100 * sum(st.values()) / sum(tot.values()); a_all = 100 * sum(ai.values()) / sum(tot.values())
    ax.set_title(f"UNSW-NB15 (6 pcaps): event-level detection — overall {s_all:.1f}% → {a_all:.1f}%", fontsize=11, loc="left")
    ax.legend(loc="lower right", frameon=False)
    fig.savefig(FIG / "fig5-2_unsw_recall.png"); plt.close(fig)


def precision_numbers():
    d = load("cic_scores.json")
    days = d["days"]
    rules = d["ai_rules"]
    wed_fri_sids = {3000001, 3000002, 3000003, 3000004, 9600001, 9600002, 9600003, 9600004, 9700001, 9700002, 9700003}
    s_wf = [days[x]["stock_alerts"] for x in ("Wednesday", "Friday")]
    stock_wf = (sum(s.get("attack", 0) for s in s_wf), sum(s.get("benign", 0) for s in s_wf))
    stock_all = (sum(v["stock_alerts"].get("attack", 0) for v in days.values()),
                 sum(v["stock_alerts"].get("benign", 0) for v in days.values()))
    # 9500002 is a Tuesday rule; its 79 Friday hits (all PortScan-labelled) belong to the Wed+Fri window.
    ai_wf = [sum(rules[str(s)]["attack"] for s in wed_fri_sids) + 79, sum(rules[str(s)]["benign"] for s in wed_fri_sids)]
    ai_all = (sum(r["attack"] for r in rules.values()), sum(r["benign"] for r in rules.values()))
    ai_all_ex = (ai_all[0], ai_all[1] - rules["7600004"]["benign"] - rules["7600007"]["benign"])
    return {"stock_wf": stock_wf, "ai_wf": tuple(ai_wf), "stock_all": stock_all, "ai_all": ai_all, "ai_all_ex": ai_all_ex}


def fig_precision():
    p = precision_numbers()
    pct = lambda t: 100 * t[0] / (t[0] + t[1])
    groups = ["Wednesday + Friday\n(noisy raw captures)", "All four days", "All four days, excl.\nrules 7600004/7600007"]
    stock = [pct(p["stock_wf"]), pct(p["stock_all"]), pct(p["stock_all"])]
    ai = [pct(p["ai_wf"]), pct(p["ai_all"]), pct(p["ai_all_ex"])]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = range(3); w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], stock, w, color=STOCK, label="Stock ET Open")
    b2 = ax.bar([i + w / 2 for i in x], ai, w, color=AI, label="AI-authored rules")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.1f}%", ha="center", fontsize=8)
    ax.set_xticks(list(x), groups, fontsize=8.5)
    ax.set_ylabel("Label-matched alerts on attack flows (%)")
    ax.set_ylim(0, 112)
    ax.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.12))
    fig.savefig(FIG / "fig5-3_precision.png"); plt.close(fig)
    return p


def fig_coverage():
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    labels = ["Stock ET Open\n(≥1 true-positive alert)", "Stock + AI-authored rules\n(≥1 true-positive alert)", "Model triage findings\n(category identified)"]
    cic = [8, 12, 13]
    uf = load("unsw_findings.json")
    ud = load("unsw_scores.json")
    tot = ud["gt_events_tcpudp"]
    u_stock = sum(1 for c in tot if ud["detected_tcpudp"]["stock"].get(c, 0) > 0)
    u_ai = sum(1 for c in tot if ud["detected_tcpudp"]["stock+cic+unsw"].get(c, 0) > 0)
    u_model = sum(1 for c in uf["categories"] if uf["coverage_tcpudp"][c][0] > 0)
    unsw = [u_stock, u_ai, u_model]
    x = range(3); w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], [100 * v / 14 for v in cic], w, color=[STOCK, AI, MODEL], edgecolor="black", linewidth=0.5)
    b2 = ax.bar([i + w / 2 for i in x], [100 * v / 9 for v in unsw], w, color=[STOCK, AI, MODEL], hatch="//", edgecolor="black", linewidth=0.5)
    for b, v, n in [(b, v, 14) for b, v in zip(b1, cic)] + [(b, v, 9) for b, v in zip(b2, unsw)]:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, f"{v}/{n}", ha="center", fontsize=9)
    ax.set_xticks(list(x), labels, fontsize=8.5)
    ax.set_ylabel("Attack categories covered (%)")
    ax.set_ylim(0, 115)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor="white", edgecolor="black", label="CIC-IDS2017 (14 categories)"),
                       Patch(facecolor="white", edgecolor="black", hatch="//", label="UNSW-NB15 (9 categories)")],
              loc="upper left", frameon=False, fontsize=8.5)
    fig.savefig(FIG / "fig5-4_category_coverage.png"); plt.close(fig)
    return {"cic": cic, "unsw": unsw}


def fig_rule_audit():
    rows = list(csv.DictReader(open(RES / "rule_audit.csv")))
    def status(r):
        if r["load_status"] == "deleted":
            return "Deleted by model"
        if r["load_status"] == "fails to load":
            return "Fails to load"
        if r["load_status"] == "loads, cannot fire":
            return "Loads, can never fire"
        fired = r["cic_alerts"] if r["dataset"] == "CIC" else r["unsw_alerts"]
        if fired:
            return "Fired on replay"
        if r["sid"] in ("9000001", "9000002", "9000003", "9000005"):
            return "Replayed, never fired"
        return "Never replayed"
    order = ["Fired on replay", "Replayed, never fired", "Never replayed", "Loads, can never fire", "Fails to load", "Deleted by model"]
    colors = [AI, "#7fa7c9", "#cfd6dd", "#e3b27a", "#c0392b", "#555555"]
    counts = {ds: {s: 0 for s in order} for ds in ("CIC", "UNSW")}
    for r in rows:
        counts[r["dataset"]][status(r)] += 1
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    for i, ds in enumerate(("UNSW", "CIC")):
        left = 0
        for s, c in zip(order, colors):
            v = counts[ds][s]
            if v:
                ax.barh(i, v, left=left, color=c, edgecolor="white", label=s if i == 1 else None)
                ax.text(left + v / 2, i, str(v), ha="center", va="center", fontsize=8,
                        color="white" if c in (AI, "#c0392b", "#555555") else "black")
                left += v
    ax.set_yticks([0, 1], ["UNSW-NB15\n(18 rules)", "CIC-IDS2017\n(32 rules)"])
    ax.set_xlabel("AI-authored rule definitions")
    ax.legend(ncol=3, fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.35))
    fig.savefig(FIG / "fig5-5_rule_audit.png"); plt.close(fig)
    return counts


def fig_alert_volume():
    days = ["Tue", "Wed", "Thu", "Fri"]
    tuned = [2404, 381, 25406, 263]
    raw = [1842712, 2310105, 1346596, 1412449]
    unsw = [("pcap 1", 997), ("pcap 3", 893), ("pcap 4", 625), ("pcap 5", 905), ("pcap 10", 799), ("pcap 14", 854)]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    w = 0.38
    x = list(range(4))
    ax.bar([i - w / 2 for i in x], tuned, w, color=AI, label="CIC tuned (Monday suppressions)")
    ax.bar([i + w / 2 for i in x], raw, w, color=STOCK, label="CIC raw (no suppression)")
    xu = [5 + i * 0.6 for i in range(6)]
    ax.bar(xu, [v for _, v in unsw], 0.45, color=MODEL, label="UNSW-NB15 raw")
    ax.set_yscale("log")
    ax.set_xticks(x + xu, days + [n for n, _ in unsw], fontsize=8, rotation=0)
    for lab in ax.get_xticklabels()[4:]:
        lab.set_rotation(45)
    ax.set_ylabel("Alerts (log scale)")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.savefig(FIG / "fig4-2_alert_volume.png"); plt.close(fig)


def fig_unsw_matrix():
    uf = load("unsw_findings.json")
    cats = uf["categories"]
    runs = list(uf["runs"])
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    for i, r in enumerate(runs):
        for j, c in enumerate(cats):
            main = c in uf["runs"][r]["main"]
            touched = c in uf["runs"][r]["any"]
            if r == "unsw-3" and c == "Worms":
                main = True  # SQL Slammer named explicitly; matches the single GT Worms event exactly
            col = AI if main else ("#b9cde0" if touched else "#f2f2f2")
            ax.add_patch(plt.Rectangle((j, i), 0.95, 0.9, color=col))
    ax.set_xlim(0, len(cats)); ax.set_ylim(len(runs), 0)
    ax.set_xticks([j + 0.47 for j in range(len(cats))], cats, rotation=30, ha="right", fontsize=8)
    ax.set_yticks([i + 0.45 for i in range(len(runs))], runs, fontsize=8)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=AI, label="Main category of a finding"), Patch(color="#b9cde0", label="Finding touches category"),
                       Patch(color="#f2f2f2", label="Not identified")], ncol=3, fontsize=7.5, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, 1.2))
    fig.savefig(FIG / "fig4-3_unsw_findings_matrix.png"); plt.close(fig)


def box(ax, x, y, w, h, text, fc="#eef3f8", ec="#1f4e79", fs=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, text="", fs=7.5, color="#333333", off=(0, 0.12)):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2))
    if text:
        ax.text((x1 + x2) / 2 + off[0], (y1 + y2) / 2 + off[1], text, ha="center", va="bottom", fontsize=fs, color=color)


def fig_agentic_loop():
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.6); ax.axis("off")
    box(ax, 0.1, 3.6, 2.5, 1.3, "Hosted LLM\n(Claude / DeepSeek)\nvia provider adapter", bold=True, fs=8)
    box(ax, 4.25, 3.6, 2.5, 1.3, "Triage engine\n(tool-calling loop,\nmax 100 turns)", bold=True, fs=8)
    box(ax, 8.4, 3.6, 2.5, 1.3, "Tool layer\n(8 validated tools,\npath allowlist)", bold=True, fs=8)
    box(ax, 8.4, 0.3, 2.5, 1.9, "Sensor data & engine\neve.json · fast.log\nsuricata.yaml (read-only)\nrules/generated/\nSuricata replay", fc="#fbf1e6", ec="#d9822b", fs=8)
    box(ax, 0.1, 0.3, 2.5, 1.9, "Outputs\nDetection rules\n(auto-deploy)\nSuppress proposals\n(human approval)", fc="#fbf1e6", ec="#d9822b", fs=8)
    box(ax, 4.25, 0.75, 2.5, 1.0, "Web UI (SSE stream)\nand session transcript", fc="#f4f4f4", ec="#777777", fs=8)
    arrow(ax, 4.25, 4.6, 2.6, 4.6, "① history + tools", off=(0, 0.08))
    arrow(ax, 2.6, 3.9, 4.25, 3.9, "② tool call", off=(0, -0.38))
    arrow(ax, 6.75, 4.6, 8.4, 4.6, "③ execute", off=(0, 0.08))
    arrow(ax, 8.4, 3.9, 6.75, 3.9, "⑤ result", off=(0, -0.38))
    arrow(ax, 9.65, 3.6, 9.65, 2.2, "④ query / replay", off=(-1.0, 0))
    arrow(ax, 5.5, 3.6, 5.5, 1.75, "every event", off=(0.62, 0))
    arrow(ax, 4.35, 3.6, 2.6, 2.2, "⑥ report, rule\nor proposal", off=(-0.3, -0.1))
    ax.text(5.5, 5.3, "Steps ①–⑤ repeat until the model replies without a tool call", ha="center", fontsize=8, style="italic")
    fig.savefig(FIG / "fig3-3_agentic_loop.png"); plt.close(fig)


def fig_safety_asymmetry():
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    ax.set_xlim(0, 11); ax.set_ylim(0, 5); ax.axis("off")
    box(ax, 0.1, 2.0, 2.0, 1.0, "Alert category\ninvestigated", bold=True, fs=8)
    box(ax, 2.7, 2.0, 1.9, 1.0, "Model verdict", fc="#fff7e0", ec="#b8860b", bold=True, fs=8)
    box(ax, 5.4, 3.5, 2.5, 1.1, "Write detection rule,\nvalidate by\nSuricata replay", fs=8)
    box(ax, 8.5, 3.5, 2.4, 1.1, "Auto-deploy\n(rules/generated/)", fc="#e6f2e6", ec="#2e7d32", bold=True, fs=8)
    box(ax, 5.4, 0.4, 2.5, 1.1, "Propose suppress line\n(in report only,\nnot applied)", fs=8)
    box(ax, 8.5, 0.4, 2.4, 1.1, "Human approval,\nthen threshold.config", fc="#fdecea", ec="#c0392b", bold=True, fs=7.5)
    arrow(ax, 2.1, 2.5, 2.7, 2.5)
    arrow(ax, 4.6, 2.8, 5.4, 4.0, "threat", off=(-0.4, 0.05))
    arrow(ax, 4.6, 2.2, 5.4, 0.95, "benign / noise", off=(-0.65, -0.35))
    arrow(ax, 7.9, 4.05, 8.5, 4.05)
    arrow(ax, 7.9, 0.95, 8.5, 0.95)
    ax.text(8.2, 2.55, "Wrong-way-safe: a bad rule over-alerts.\nWrong-way-unsafe: a bad suppression blinds\nthe sensor, so a human decides.",
            ha="center", va="center", fontsize=7.5, style="italic", color="#444444")
    fig.savefig(FIG / "fig3-4_safety_asymmetry.png"); plt.close(fig)


def fig_experiment1():
    path = RES / "experiment1.json"
    if not path.exists():
        return None
    e = json.loads(path.read_text())
    conds = [("full", "Full context", AI), ("bare", "Alerts only", MODEL)]
    def m(c):
        f, r = e[c]["findings"], e[c]["replay"]
        runs = f["per_run"].values()
        return {
            "Categories identified\n(of 9, union of 3 runs)": len(f["union_main"]),
            "GT events covered\nby findings (%)": 100 * f["covered_tcpudp"] / f["tcpudp"],
            "TCP/UDP detection with\nthe condition's rules (%)": 100 * r["cond_detected"] / r["tcpudp_events"],
            "Evidence-backed outcome\nstatements (3 reports)": sum(x["outcome_statements"] - x["outcome_unconfirmed"] for x in runs),
        }
    vals = {c: m(c) for c, _, _ in conds}
    base = 100 * e["full"]["replay"]["base_detected"] / e["full"]["replay"]["tcpudp_events"]
    keys = list(vals["full"])
    fig, axes = plt.subplots(1, 4, figsize=(7.6, 2.9))
    for ax, k in zip(axes, keys):
        bars = ax.bar([0, 1], [vals[c][k] for c, _, _ in conds], color=[col for _, _, col in conds], width=0.6)
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, v * 1.02 + 0.2, f"{v:.1f}" if "%" in k else f"{v:.0f}", ha="center", fontsize=8)
        if "detection" in k:
            ax.axhline(base, color="#555555", ls="--", lw=0.9)
            ax.text(1.35, base, f"stock+CIC\n{base:.1f}%", fontsize=6.5, va="center", color="#555555")
        ax.set_xticks([0, 1], ["Full", "Alerts\nonly"], fontsize=8)
        ax.set_title(k, fontsize=7.8)
        ax.set_ylim(0, max(vals[c][k] for c, _, _ in conds) * 1.25 + 1)
        ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(FIG / "fig5-6_experiment1.png"); plt.close(fig)
    return vals


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    fig_agentic_loop(); fig_safety_asymmetry()
    fig_alert_volume(); fig_unsw_matrix()
    fig_cic_recall(); fig_unsw_recall()
    p = fig_precision(); cov = fig_coverage(); audit = fig_rule_audit()
    print("experiment1:", fig_experiment1())
    print("precision inputs:", p)
    print("coverage:", cov)
    print("audit:", audit)
    print("saved:", sorted(x.name for x in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
