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

This section describes the CIC-IDS2017 set-up, which is **frozen** (`config/suricata.yaml`,
`config/threshold.config`). UNSW-NB15 has its own, separate set-up — see §3.7.

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

Use `scripts/run_suricata.sh <cic|unsw> <profile> <pcap> <run-name>` for replays: it names the
config used and writes a fresh `logs/<run-name>/` (Suricata appends to an existing eve.json —
reusing a folder silently doubled the Friday tuned input once).

### 3.7 Separate set-up per dataset; UNSW-NB15 baseline v2

CIC-IDS2017 and UNSW-NB15 never share configs or AI rule files (supervisor's suggestion), so
work on one cannot break the other:

- CIC: `config/suricata.yaml` (frozen) and experiment profiles in `config/cic/`; AI rules in
  `rules/generated/cic/`.
- UNSW: profiles in `config/unsw/`; AI rules in `rules/generated/unsw/`.
  `config/unsw/baseline.yaml` is the **frozen UNSW baseline v2**: ET Open + Snort Community +
  Stamus lateral + PT Open + disabled ET/Snort rule families re-enabled by attack type
  (`rules/extra/`). No Nmap ruleset (it wrecked CIC precision for no UNSW gain).

**Why the family selection:** families were chosen from the eve.json traffic profile (services
under attack), never from the labels. Control result: enabling *all* disabled rules gave 31%
detection but 47x more alerts on non-attacker hosts; the selection gave 25.7% with almost no
extra noise. UNSW has no benign-only day, so UNSW runs are always raw (no suppressions).

### 3.8 Evaluation integrity — do not break these

- The model must never see ground truth. Tools only open `logs/`, `config/`, `rules/`,
  `data/pcaps/` (allowlist in `src/tools.py`); labels, notes, docs, transcripts and results are
  refused. Earlier CIC runs leaked via the label folder and PROJECT_STATE — documented in the report.
- Never choose rules, rule families or SIDs by checking which ones match ground-truth events.
- Never give the model anything derived from labels (category names, "undetected" lists).
- `lookup_vulnerability` uses only the local NVD copy (`data/kb/`, rebuild with
  `python -m src.kb.build_nvd`) and refuses dataset/generator terms; any live web lookup must
  use a domain allowlist, not a blocklist.
- Six UNSW captures (17 Feb day) are the development set. Final claims need the untouched
  hold-out captures from the 22 Jan day (`data/pcaps/unsw/day1/`). Hold-out = 22 Jan captures 1, 3, 6 (inside
  the GT attack window, 11:00-14:00 UTC) for detection, plus 25 and 50 (no labelled attacks) as an
  unseen-normal-traffic false-positive check. Baseline v2 there: 29.5–29.6% (across replays).
- **Normal-host test (decided 4 Oct 2026).** The hunt profile's `test_rule` tool treats traffic
  between HOME_NET hosts (59.166.0.0/24 clients → 149.171.126.0/24 servers) as known-good. Source:
  the dataset's published testbed description (Moustafa & Slay 2015; summarised by FKIE COMIDDS:
  "Server 1 and 3 generate normal traffic, while server 2 generates malicious traffic").
  It is documented topology, not per-event ground truth. The tool reports counts by host role only.
  It cannot test POP3/SIP/SMB rules — no internal traffic uses those protocols in UNSW.
- **Hunt profile has no attacker range in its prompt** (a real engineer would not know it). This
  makes hunt differ from plain/research in two ways (procedure + context); state it in the report.

### 3.9 Experiment profiles

Every agent run uses a named profile (`src/profiles.py`): dataset, Suricata config, writable rule
file, tool set, prompt, blocked files. The UI, CLI and batch runner all select by profile name.
A profile used in a scored run is **frozen** — change means a new profile, because transcripts and
`docs/results/` reference profiles by name.

### 3.10 Scoring and final-evaluation decisions (team, 4 Oct 2026)

- **Round gains are attributed by the AI rules' own alerts**, not full-replay minus baseline log.
  Replays are not deterministic (thresholds); the old metric counted that variance as gain
  (hunt R1: +82 by the old metric, 6 attributable). All conditions are re-scored this way, and
  the corrected figures replace earlier headlines (e.g. plain R2 36.3%).
- **Hold-out rule set, fixed before the hold-out is seen:** non-topology AI rules only (signature +
  behavioural, by the rule-class audit), reported per condition and combined.
- **Remaining runs:** deepseek-v4-pro for every condition. Finish hunt R1 (captures 1, 10).
  `unsw-v2-hunt2` (technique-level rules) only if done by ~8 Oct. Plain/research round 3 dropped.

---

## 4. Experiments — this is what makes it research

**Status (4 Oct 2026, final):** Exp 1, 2, 3 done. Exp 3 = AI rounds on UNSW baseline v2, conditions plain,
research, hunt, hunt2 (`src/eval/rounds.py`, within-replay attribution, §3.10). Genuine gain dev / hold-out:
plain +0.08 / +0.11, research +0.33 / +0.28, hunt +1.21 / +1.53, hunt2 (hunt + keyword tool) +0.91 / +1.06;
0 AI alerts on benign hold-out captures; all four combined ≈ +2.2 pts on hold-out. Hunt gain coincides with the
4 Oct provider fix (DeepSeek reasoning_content was dropped); hunt vs hunt2 differ within run-to-run variation.
~77% of attack events carry data (content-detectable), baseline catches ~24% of those: the gap is unwritten
signatures (`src/eval/detectable.py`). Report (81 pp) and deck (27 slides) rebuilt with all of it.
**Submission versions (8 Oct 2026):** HIT401 caps the final report at 4,000–5,000 words, so the submitted report is
`docs/Final_Report_Group13.docx` (built by `docs/build_report_v2.py`, ~4,250 words of prose, 19 figures, appendices
A–D; `docs/update_fields.py` fills the lists and exports the PDF). The 81-page draft is kept as the detailed record.
The video deck (5–10 min allowed; 13 slides, ~8 min) is `docs/Group13_Video_Presentation.pptx` (`docs/build_video_deck.js`, script in `docs/video_script.md`).

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
│   ├── pcaps/                  # gitignored — CIC *.pcap; unsw/ (dev); unsw/day1/ (hold-out)
│   ├── labels/                 # ground truth — TrafficLabelling/ (CIC), "source trouth unsw"/ (UNSW)
│   └── kb/                     # gitignored — local NVD knowledge base for lookup_vulnerability
├── rules/
│   ├── suricata.rules          # ET Open ruleset — NEVER edit directly
│   ├── extra/                  # other open rulesets + re-enabled families (UNSW baseline v2)
│   ├── generated/cic/          # AI rules written on CIC-IDS2017 (+ triage reports)
│   ├── generated/unsw/         # AI rules written on UNSW-NB15 (v1, bare, rounds_plain/research)
│   ├── snapshots/              # rule-file state after each run (not loaded)
│   └── normal.rules            # old approach, superseded, kept for history
├── config/
│   ├── suricata.yaml           # CIC triage config — FROZEN
│   ├── threshold.config        # CIC suppressions (Monday baseline) — FROZEN
│   ├── cic/  unsw/             # per-dataset Suricata profiles (unsw/baseline.yaml = UNSW v2)
│   └── classification.config
├── scripts/run_suricata.sh     # replay a pcap with a named profile into logs/<run>/
├── logs/                       # per-run subdirectories, gitignored
├── triage-*.txt                # session transcripts (evidence; never edit)
├── src/                        # engine, tools, prompts (DATASETS profiles), providers, CLI/server,
│   ├── batch_transcript.py     #   unattended runs → transcript
│   ├── kb/                     #   NVD knowledge-base builder
│   └── eval/                   #   ground-truth scoring, rule audit, figures, experiments
└── docs/                       # report draft + build_final_report.py, deck + build_deck.js,
                                #   results/ (JSON/CSV), figures/, meeting minutes
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

**UNSW-NB15**, UNSW Canberra (Moustafa & Slay 2015) — second dataset, added at the
supervisor's request (Week 9). <https://research.unsw.edu.au/projects/unsw-nb15-dataset>

- Ground truth: `NUSW-NB15_GT.csv` (one row per attack event, 9 categories).
- Layout: attackers 175.45.176.0/24 → servers 149.171.126.0/24; normal clients 59.166.0.0/24.
- Dev set: 17 Feb captures 1, 3, 4, 5, 10, 14 (file 27 was truncated). Hold-out: 22 Jan captures.
- No benign-only day → no baseline tuning; headline recall on TCP/UDP events only.

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

1. ~~**Human-in-the-loop.**~~ Decided by the team 4 Oct 2026: §3.4 adopted as designed —
   detection rules auto-deploy, suppressions need human approval (already enforced in the engine).
   Confirm with the supervisor.
2. ~~**Narrow or wider claim.**~~ Decided 4 Oct 2026: **split claim**, because that is what the
   evidence shows. Yes for triage with sensor-available context (CIC 13/14, UNSW 8/9 categories
   identified; context adds outcome evidence, Exp 1). Partial for raising detection over a strong
   human-tuned baseline: triage-driven conditions add a fraction of a point; the hunt workflow (with
   reasoning carried) adds +1.2 pts dev / +1.5 pts hold-out, 0 FPs — confounded with the 4 Oct fix.
3. ~~**Label join.**~~ Resolved: alerts join to CIC flows by 5-tuple + time window (±120 s;
   labels are minute-resolution, 12-hour clock, ADT) and to UNSW events by endpoints + time
   (±2 s). See `src/eval/cic_score.py`, `src/eval/unsw_score.py`.
4. ~~**Network-based vs host-based IDS.**~~ Decided 4 Oct 2026: network-based; host-based is
   future work. State it in the report.
5. **Project charter and management plan.** Assigned in meeting 01, not mentioned since,
   now overdue. Confirm whether still required.

---

## 10. Things to raise with the supervisor

- Which dataset he expects — he said "open source datasets" without naming any, and they
  are not interchangeable.
- Whether the project charter is still required.
- The human-in-the-loop decision (question 1 above).
