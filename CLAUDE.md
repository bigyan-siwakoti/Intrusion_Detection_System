# CLAUDE.md — Capstone Group 13

Read this before doing anything in this repo.

This file holds what is **true and decided** about the project, and **why**. It is not a
session diary. Update it when a decision changes, a constraint arrives, or an open
question closes — not on a schedule.

---

## 1. What this project is

An open-source, rule-based intrusion detection system that uses a generative language
model to automate the alert-handling work currently done by a human analyst.

**The research question (the spine):**
Can an LLM replace the human analyst in the alert-handling loop of a rule-based IDS —
and what context does it need to do that job well?

This is a question, not a feature. The IDS pipeline is the *apparatus* that lets us
measure the answer. "We built an AI-augmented IDS" is not the deliverable.

**Team:** Bigyan Siwakoti, Irab Baral, Binay Siwakoti, Shashwat Acharya
**Supervisor:** Prof. Bharanidharan Shanmugam, Charles Darwin University
**Semester:** S2 2026 — teaching 21 Jul – 17 Oct, exams 23–31 Oct
**Unit:** [course code / name — fill in]

---

## 2. Hard constraints — do not violate

These come directly from the supervisor. If a proposed change breaks one, say so before
proceeding.

1. **Open-source / open-access only.** Source code must be downloadable. Commercial
   products are explicitly out.
2. **No machine learning.** Stated twice, unprompted, and vetoed when raised. No ML
   detection, no ML framing, no ML papers as justification.
3. **Generative AI is the automation layer, not the detector.** Hosted model APIs called
   at points where a human or a local library currently does the work.
4. **Zero-day is out of scope for now.** Explicitly rejected as a scope shift. Focus is
   rule-based detection. Do not reintroduce it.
5. **Understand before building.** Vertical and horizontal understanding of IDS before
   design decisions.

---

## 3. Locked design decisions

Each of these was reached by working a specific flaw. The **why** matters as much as the
what — it is what stops the flaw being quietly reintroduced.

### 3.1 Detection: alert-only rules, no `pass`

Rules are `alert` only. We do **not** use Suricata `pass` rules.

**Why:** a `pass` match on a TCP connection passes the *entire flow* and Suricata stops
scanning it. An attacker whose opening packets look normal gets the rest of the
connection uninspected. That is a structural bypass at the centre of the architecture,
and no amount of careful rule writing fixes it. Alert-only keeps every packet inspected
for the life of every connection.

**Also note:** Suricata does not evaluate rules in file order. Default action order is
pass → drop → reject → alert, so "put the catch-all last in the file" does nothing.
Do not rely on file position for precedence.

### 3.2 Stock community ruleset + threshold-based suppression

~~(Superseded. Original approach was hand-written normality rules that fire on
negation. Replaced with the approach below after baseline profiling work.)~~

Start with the **ET Open ruleset** (52,647 rules, pulled via `suricata-update`). Run
benign traffic (Monday CIC-IDS2017). Every alert on known-benign traffic is a false
positive — suppress it in `config/threshold.config` with a documented reason. The tuned
sensor is the baseline: anything it alerts on attack-day traffic is a real detection
candidate.

**Why the change:** the normality-encoding approach required writing rules from scratch
for every service. Starting from a mature community ruleset and tuning is what a real SOC
engineer does, produces a wider detection surface immediately, and is more defensible in
the report.

**Key principle preserved:** rules are still `alert` only (§3.1 still holds). All tuning
lives in `threshold.config` — the ET Open ruleset (`rules/suricata.rules`) is never
edited directly. This keeps the community rules intact and all local decisions in one
auditable file.

**Baseline definition (explicit decision):** normal ≡ everything CIC-IDS2017 Monday
triggered. 80 unconditional suppressions. Consequence: any genuinely malicious traffic
present in the benign-labelled capture is defined as normal. Accepted because Monday is
the labelled benign corpus (529,918 flows, all BENIGN per ground truth). Revisit if a
Tue–Fri detection is traced to a Monday-suppressed SID.

**The old `rules/normal.rules` is kept in the repo for history but is not loaded.**

### 3.3 Context bundle, not a bare packet

When an alert fires, assemble a bundle and send *that* to the model:

1. **Source history** — flows from this source IP over the last 30 days, first seen,
   usual pattern. (Query over `eve.json`.)
2. **Destination context** — from `config/assets.txt`, a hand-maintained flat file.
3. **Concurrent activity** — anything else from that source or to that destination in a
   ±5 minute window. (Query over `eve.json`.)
4. **Rule history** — how often this rule has fired and how previous alerts resolved.

**Why:** a human analyst's real work is enrichment and correlation — answers that come
from *outside* the packet. A model given only the packet is being asked to decide on
whether traffic looks unusual in isolation, which is the *input* to the decision, not the
decision. This closes two of the analyst's four questions using data we already have.

**Stated limitation:** no threat-intel reputation, no malware sandboxing, no
cross-organisation signal. Two of four, not four. Say this in the report.

### 3.4 Two exits from the LLM, with a safety asymmetry

The model chooses between:

- **Threat** → author a detection rule → validate → **auto-deploy**
- **Unprofiled but legitimate** → author a suppress rule for `threshold.config` →
  validate → **human approval required**

**Why the two exits:** most alerts from a tuned sensor hitting new traffic are benign true
positives — legitimate traffic the baseline didn't cover. With only one exit the model can
only add detection rules forever and never reduce the noise that produced the false alarm.

**Why the asymmetry:** a model that resolves everything as "legitimate, widen the profile"
degrades the IDS to passing everything. Wrong-way-safe is an over-alerting IDS; wrong-way-
unsafe is a blind one.

### 3.5 The model authors rules; it never classifies traffic

Detection stays rule-based and inspectable at all times. This is the commitment that
keeps the project inside constraint 2 and 3.

### 3.6 Offline pcap replay, not live capture

Run `suricata -r <file>.pcap`. No live interface, no inline mode, no TLS termination.

**Why:** it is what the supervisor asked for (download datasets, run them, see if it
detects), and it sidesteps the sensor-placement and HTTPS questions that stalled us in
meeting 3. Sensor placement is a later problem, not a week-5 one.

---

## 4. Experiments — this is what makes it research

### Experiment 1 — does context matter? **(the spine)**

Run the same alerts through the model twice: **bare packet** vs **full context bundle**.
Score triage decisions against CIC-IDS2017 ground-truth labels.

Either result is a finding. "Context improved accuracy by X%" and "context made no
measurable difference" are both worth reporting. A demo can only succeed or fail; a
comparison always produces data.

### Experiment 2 — are the authored rules any good?

For traffic judged a threat: does the rule validate (`suricata -T`), does it catch the
attack on replay, does it over-fire on benign traffic? Baseline against the corresponding
Emerging Threats rule as the human-authored comparison.

Metrics: precision, recall, false-positive rate, rule validity, latency.

### Experiment 3 — does the profile converge?

Replay benign traffic over N cycles with the normality-widening loop enabled. Does alert
volume fall across iterations? A falling curve is a system that improves without ML.

**Discipline:** tune the parameters, not the question. Rules, bundle contents, prompts and
thresholds should all move as we learn. The thing being measured stays fixed. Before each
run, write down what we expect — when we are wrong, that gap is the finding.

---

## 5. Environment

- **Windows + WSL (Ubuntu).** VS Code connected to WSL via the WSL extension.
- **The project lives in the Linux filesystem** — `~/capstone-ids/`. Never under
  `/mnt/c/...`; crossing the boundary is slow on multi-GB pcaps.
-  Suricata 8.0.6 (OISF PPA). Use version-matched docs:
  docs.suricata.io/en/suricata-8.0.6/ — a lot of tutorials online target 6.x and
  some rule keywords and eve.json fields have changed.
- `jq` — the context bundle is built out of `jq` queries over `eve.json`. Core, not optional.
- `tshark` / `editcap` — pcap slicing.
- Python 3 in a venv. Never system Python.

**Slice before iterating:**

```bash
editcap -r Monday-WorkingHours.pcap slices/monday-10k.pcap 1 10000
```

Iterate against the slice; run the full file only to confirm a result. This is the
difference between ten experiments a day and two.


---

## 6. Repo layout

```
~/capstone-ids/
├── CLAUDE.md
├── PROJECT_STATE.txt           # detailed project state for session continuity
├── data/
│   ├── pcaps/                  # gitignored — multi-GB
│   ├── slices/                 # small cuts for fast iteration
│   └── labels/                 # ground-truth CSVs (TrafficLabelling/)
├── rules/
│   ├── suricata.rules          # ET Open ruleset — NEVER edit directly
│   ├── normal.rules            # old approach, superseded, kept for history
│   └── generated/              # rules authored by the LLM
├── config/
│   ├── suricata.yaml           # project-local config (HOME_NET, checksums, paths)
│   ├── threshold.config        # all suppress/threshold tuning lives here
│   ├── classification.config   # copied from ET Open
│   └── assets.txt              # hand-maintained destination context
├── logs/                       # per-run subdirectories, gitignored
├── src/
│   ├── bundle/                 # builds the context bundle from eve.json
│   ├── llm/                    # API calls, prompts
│   └── eval/                   # scoring against ground truth
└── docs/                       # minutes, charter, findings log
```

**`.gitignore` the pcaps and logs from the first commit.** Multi-GB files in git are
painful to undo.

---

## 7. Data

**CIC-IDS2017**, Canadian Institute for Cybersecurity, UNB.
<https://www.unb.ca/cic/datasets/ids-2017.html>

- Capture ran Mon 3 July – Fri 7 July 2017.
- **Monday is benign-only** → this is the corpus the normality profile is built from.
- Tuesday–Friday contain attacks → test set.
- Take the **PCAPs**, not the ML CSVs (pre-extracted flow features, unusable by Suricata).
- Take the labelled flows separately as ground truth for Experiment 1.
- Verify each download: `md5sum -c <file>.md5`.

---

## 8. Conventions

- **Git:** one repo, four GitHub accounts. Everyone commits their own work even when
  sharing one machine. There is no other record of individual contribution, and the
  supervisor has already noticed the group tends to speak through one person.
- Suppress lines in `threshold.config` carry a comment stating **why this alert is
  normal for this capture**. The ET Open ruleset is never edited directly.
- Generated rules land in `rules/generated/` and are never hand-edited in place — if a
  generated rule is wrong, that is a finding, so record it.
- Record expected outcome before each experimental run.

---

## 9. Open questions — genuinely undecided

Do not invent answers to these. Flag them.

1. **Human-in-the-loop.** §3.4 proposes approve-normality / auto-deploy-detection. The
   team has not formally adopted it. Raised with the supervisor in meeting 3 and left
   unresolved.
2. **Narrow or wider claim.** Narrow = "automates rule authoring given a decision".
   Wider = "automates triage with sensor-available context". Experiment 1's framing
   depends on this.
3. **Label join.** CIC-IDS2017 ground truth is per-flow; our alerts come from `eve.json`.
   How cleanly these join is unknown until inspected, and Experiment 1's strength depends
   on it.
4. **Network-based vs host-based IDS.** Asked in meeting 3, not settled by the supervisor.
5. **Project charter and management plan.** Assigned in meeting 01, not mentioned since,
   now overdue. Confirm whether still required.

---

## 10. Things to raise with the supervisor

- Which dataset he expects — he said "open source datasets" without naming any, and they
  are not interchangeable.
- Whether the project charter is still required.
- The human-in-the-loop decision (question 1 above).
