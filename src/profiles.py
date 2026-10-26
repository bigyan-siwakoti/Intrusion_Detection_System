"""Experiment profiles — one per agent condition.

A profile fixes everything a run depends on: dataset, Suricata config, the one writable rule file,
the tool set, the prompt, and the files the model may not open. The UI, CLI and batch runner select
by profile name, and transcripts record it ("Dataset:" header line, read by src/eval/rounds.py).

A profile used in a scored run is FROZEN: to change one, add a new profile. Results and transcripts
refer to profiles by name.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

TRIAGE_TASK = "Triage the alerts in {eve_path}. Follow the triage procedure step by step."
HUNT_TASK = ("Hunt for attack activity in {eve_path} that the deployed rules do not detect, and write detection "
             "rules for it. Follow the hunting procedure step by step.")

UNSW_V2_CONTEXT = (
    "- UNSW-NB15 network layout: HOME_NET is 149.171.126.0/24 (servers) and 59.166.0.0/24 (clients); "
    "known attacker range is 175.45.176.0/24.\n"
    "- The sensor runs a strengthened baseline: ET Open plus additional open rulesets selected for the services seen "
    "in this network. Suricata uses {cfg} (read-only). Write new detection rules to {rules} — it is the only "
    "generated rule file loaded for validation runs. Rules written in earlier rounds are already in that file and loaded; "
    "concentrate on attack activity they and the baseline do not yet cover. UNSW pcaps are in data/pcaps/unsw/.\n"
    "- Before writing a rule, use search_rules to check that no loaded rule already covers the behaviour."
)

# No attacker range: a real detection engineer does not know it (CLAUDE.md §3.8).
UNSW_HUNT_CONTEXT = (
    "- Network layout: HOME_NET is 149.171.126.0/24 (servers) and 59.166.0.0/24 (internal clients). "
    "Everything else is external.\n"
    "- The sensor runs a strengthened baseline: ET Open plus additional open rulesets selected for the services seen "
    "in this network. Suricata uses {cfg} (read-only). Write new detection rules to {rules} — it is the only "
    "generated rule file loaded for validation runs. Rules written in earlier rounds are already in that file and loaded.\n"
    "- Captures are in data/pcaps/unsw/<n>.pcap; a log directory named logs/unsw-<n>-... was produced from capture <n>. "
    "Use that capture with test_rule."
)

PROFILES = {
    "cic": {
        "dataset": "cic",
        "description": "CIC-IDS2017 alert triage (frozen CIC config, Monday-tuned suppressions).",
        "suricata_config": "config/suricata.yaml",
        "context": "- CIC-IDS2017 network layout: victims are 192.168.10.0/24, known attacker is 172.16.0.1.",
    },
    "unsw": {
        "dataset": "unsw",
        "description": "UNSW v1: ET Open + CIC AI rules, alert triage.",
        "suricata_config": "config/unsw/v1.yaml",
        "context": (
            "- UNSW-NB15 network layout: HOME_NET is 149.171.126.0/24 (servers) and 59.166.0.0/24 (clients); "
            "known attacker range is 175.45.176.0/24.\n"
            "- For this dataset, Suricata uses config/unsw/v1.yaml (read-only). Write new detection rules to "
            "rules/generated/unsw/unsw_triage.rules — it is the only generated rule file loaded for UNSW validation runs. "
            "UNSW pcaps are in data/pcaps/unsw/."
        ),
    },
    "unsw-bare": {
        "dataset": "unsw",
        "description": "Experiment 1 bare condition: alert events only, no flow/app-layer context.",
        "suricata_config": "config/unsw/bare.yaml",
        "alerts_only": True,
        "extra_blocked": ["rules/generated/unsw/unsw_triage.rules"],
        "context": (
            "- UNSW-NB15 network layout: HOME_NET is 149.171.126.0/24 (servers) and 59.166.0.0/24 (clients); "
            "known attacker range is 175.45.176.0/24.\n"
            "- For this dataset, Suricata uses config/unsw/bare.yaml (read-only). Write new detection rules to "
            "rules/generated/unsw/unsw_bare.rules — it is the only generated rule file loaded for UNSW validation runs. "
            "UNSW pcaps are in data/pcaps/unsw/."
        ),
    },
    "unsw-v2-plain": {
        "dataset": "unsw",
        "description": "Exp 3 plain: alert triage on baseline v2 + search_rules.",
        "suricata_config": "config/unsw/baseline-plain.yaml",
        "extra_tools": ["search_rules"],
        "extra_blocked": ["rules/generated/unsw/unsw_triage.rules", "rules/generated/unsw/unsw_bare.rules",
                          "rules/generated/unsw/rounds_research.rules"],
        "context": UNSW_V2_CONTEXT.format(rules="rules/generated/unsw/rounds_plain.rules", cfg="config/unsw/baseline-plain.yaml"),
    },
    "unsw-v2-research": {
        "dataset": "unsw",
        "description": "Exp 3 research: alert triage on baseline v2 + search_rules + local NVD lookup.",
        "suricata_config": "config/unsw/baseline-research.yaml",
        "extra_tools": ["search_rules", "lookup_vulnerability"],
        "extra_blocked": ["rules/generated/unsw/unsw_triage.rules", "rules/generated/unsw/unsw_bare.rules",
                          "rules/generated/unsw/rounds_plain.rules"],
        "context": UNSW_V2_CONTEXT.format(rules="rules/generated/unsw/rounds_research.rules", cfg="config/unsw/baseline-research.yaml")
                   + "\n- When an attack is confirmed but search_rules finds no deployed signature for it, use lookup_vulnerability "
                     "to research the vulnerability (product, flaw type, CVE) before writing the rule.",
    },
    "unsw-v2-hunt": {
        "dataset": "unsw",
        "description": "Exp 3 hunt: detection-engineer workflow on baseline v2 — stack rare protocol values, "
                       "write rules, every rule must pass test_rule (anti-topology gate) before it is saved.",
        "suricata_config": "config/unsw/baseline-hunt.yaml",
        "prompt": "hunt",
        "task": HUNT_TASK,
        "extra_tools": ["search_rules", "lookup_vulnerability", "stack_values", "test_rule"],
        "rule_file": "rules/generated/unsw/rounds_hunt.rules",
        "require_test": True,
        # Raised from the engine default of 100 (4 Oct): capture 1 ran out of turns right after its rules passed test_rule.
        "max_turns": 150,
        # Only its own runs and the plain baseline runs: logs of other conditions carry their rules' alerts.
        "logs_allow": r"unsw-\d+-baseline|unsw-\d+-hunt-r\d+.*|_test_rule",
        # Other UNSW configs name the attacker range in a HOME_NET comment; hunt reads only its own.
        "extra_blocked": ["rules/generated/unsw/unsw_triage.rules", "rules/generated/unsw/unsw_bare.rules",
                          "rules/generated/unsw/rounds_plain.rules", "rules/generated/unsw/rounds_research.rules"]
                         + [f"config/unsw/{f.name}" for f in sorted((_ROOT / "config/unsw").glob("*.yaml"))
                            if f.name != "baseline-hunt.yaml"],
        "context": UNSW_HUNT_CONTEXT.format(rules="rules/generated/unsw/rounds_hunt.rules", cfg="config/unsw/baseline-hunt.yaml"),
    },
    # Hunt + a keyword reference (4 Oct). Identical to unsw-v2-hunt otherwise, so the difference measures the tool.
    "unsw-v2-hunt2": {
        "dataset": "unsw",
        "description": "Exp 3 hunt2: the hunt workflow plus suricata_keywords (look up which rule keywords this "
                       "Suricata version supports) — otherwise identical to unsw-v2-hunt.",
        "suricata_config": "config/unsw/baseline-hunt2.yaml",
        "prompt": "hunt",
        "task": HUNT_TASK,
        "extra_tools": ["search_rules", "lookup_vulnerability", "stack_values", "test_rule", "suricata_keywords"],
        "tools_note": "- suricata_keywords: check that a rule keyword exists in this Suricata version (8.0.6) and see its "
                      "exact name and description, before you use a keyword you are not certain of.",
        "sid_base": 7900001,
        "rule_file": "rules/generated/unsw/rounds_hunt2.rules",
        "require_test": True,
        "max_turns": 150,
        # Its own runs and the plain baseline runs only — not the hunt condition's logs, which carry its rules' alerts.
        "logs_allow": r"unsw-\d+-baseline|unsw-\d+-hunt2-r\d+.*|_test_rule",
        "extra_blocked": ["rules/generated/unsw/unsw_triage.rules", "rules/generated/unsw/unsw_bare.rules",
                          "rules/generated/unsw/rounds_plain.rules", "rules/generated/unsw/rounds_research.rules",
                          "rules/generated/unsw/rounds_hunt.rules"]
                         + [f"config/unsw/{f.name}" for f in sorted((_ROOT / "config/unsw").glob("*.yaml"))
                            if f.name != "baseline-hunt2.yaml"],
        "context": UNSW_HUNT_CONTEXT.format(rules="rules/generated/unsw/rounds_hunt2.rules", cfg="config/unsw/baseline-hunt2.yaml"),
    },
}


# Public demo profiles (triage.bigyan.work, src/demo.py). Never used in a scored run: short turn budget, a small
# capture slice, and their own rule file that is emptied before every live run. Other AI rule files are hidden so a
# demo run starts from the human baseline only.
def _other_rule_files(keep: str) -> list:
    return [str(p.relative_to(_ROOT)) for p in sorted((_ROOT / "rules/generated").rglob("*.rules"))
            if str(p.relative_to(_ROOT)) != keep]


DEMO_CONTEXT = (
    "{layout}\n"
    "- This is a short public demonstration on a small capture slice. Suricata uses {cfg} (read-only). The capture is "
    "{pcap}; its Suricata output is in logs/{log}/. Write new detection rules only to {rules}. Keep the investigation "
    "focused: identify the main attack activity, write rules for what the loaded rules miss, and finish with the report."
)

PROFILES.update({
    "demo-cic": {
        "dataset": "cic",
        "description": "Public demo: CIC-IDS2017 Friday slice, alert triage on ET Open.",
        "suricata_config": "config/demo/cic.yaml",
        "rule_file": "rules/generated/demo/cic.rules",
        "extra_tools": ["search_rules", "lookup_vulnerability"],
        "max_turns": 150,
        "logs_allow": r"demo-cic.*",
        "extra_blocked": _other_rule_files("rules/generated/demo/cic.rules"),
        "context": DEMO_CONTEXT.format(
            layout="- CIC-IDS2017 network layout: victims are 192.168.10.0/24, known attacker is 172.16.0.1.",
            cfg="config/demo/cic.yaml", pcap="data/slices/demo-cic.pcap", log="demo-cic",
            rules="rules/generated/demo/cic.rules"),
    },
    "demo-unsw": {
        "dataset": "unsw",
        "description": "Public demo: UNSW-NB15 hold-out slice (22 Jan), alert triage on baseline v2.",
        "suricata_config": "config/demo/unsw.yaml",
        "rule_file": "rules/generated/demo/unsw.rules",
        "extra_tools": ["search_rules", "lookup_vulnerability"],
        "max_turns": 150,
        "logs_allow": r"demo-unsw.*",
        "extra_blocked": _other_rule_files("rules/generated/demo/unsw.rules"),
        "context": DEMO_CONTEXT.format(
            layout=("- UNSW-NB15 network layout: HOME_NET is 149.171.126.0/24 (servers) and 59.166.0.0/24 (clients); "
                    "known attacker range is 175.45.176.0/24."),
            cfg="config/demo/unsw.yaml", pcap="data/slices/demo-unsw.pcap", log="demo-unsw",
            rules="rules/generated/demo/unsw.rules"),
    },
})


def get_profile(name: str) -> dict:
    if name not in PROFILES:
        raise ValueError(f"unknown profile '{name}'; available: {', '.join(PROFILES)}")
    return PROFILES[name]


def task_message(name: str, eve_path: str) -> str:
    return PROFILES[name].get("task", TRIAGE_TASK).format(eve_path=eve_path)


def summary() -> list:
    """Profile list for the UI: name, dataset, description, tools."""
    return [{"name": n, "dataset": p["dataset"], "description": p["description"],
             "tools": list(p.get("extra_tools", ())), "alerts_only": p.get("alerts_only", False)}
            for n, p in PROFILES.items()]
