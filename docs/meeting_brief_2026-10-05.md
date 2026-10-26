# Supervisor meeting brief — Monday 5 October 2026 (Week 11)

## 1. One-line answer to the research question
**Split claim.** Yes for triage: with sensor context the model investigates end to end (13/14 CIC-IDS2017,
8/9 UNSW-NB15 categories) and establishes whether attacks succeeded. Partly for detection: against a strong
human-tuned baseline, triage-driven AI rules add a fraction of a point; the detection-engineering workflow
adds about +1 to +1.5 points that hold on unseen traffic with zero false alarms — real, but modest.

## 2. What we did since the last update (his Week 10 advice: "look at what real engineers do")
- Strengthened the human baseline first (what a SOC engineer would do): 9.2% → 25.7% UNSW detection.
- Found that earlier AI "gains" were mostly **topology rules** and replay noise; fixed the scoring.
- Researched detection-engineering practice (Palantir ADS, SpecterOps, threat hunting, RuleAutoPilot 2026)
  and built it into the agent: **hunt** condition with rare-value hunting and an anti-topology test gate.
- Found and fixed a real bug by watching the agent fail (DeepSeek's reasoning was being discarded).
- Added **hunt2** (keyword reference tool) to test whether rule-syntax knowledge was the bottleneck.
- Ran the **hold-out** (22 Jan captures, rule files frozen first, scored once).

## 3. Headline numbers (genuine gain = events only AI rules caught, topology rules excluded)
| Condition | Dev (6 captures) | Dev 4/5/14 (no rules written) | Hold-out | Benign captures |
|---|---|---|---|---|
| Plain triage | +0.08 pts | +0.09 | +0.11 | 0 alerts |
| Research tool | +0.33 | +0.22 | +0.28 | 0 |
| **Hunt** | **+1.21** | **+1.38** | **+1.53** | 0 |
| Hunt2 (+ keyword tool) | +0.91 | +0.92 | +1.06 | 0 |
- Baseline v2 alone: 24.9% dev, 29.5–29.6% hold-out → it generalises.
- All four conditions together on the hold-out: ≈ +2.2 pts.
- ~77% of attack events carry data a signature could see; the baseline catches only ~24% of those →
  **the gap is unwritten signatures, not undetectable traffic.**

## 4. UNSW-NB15 challenges (and what we did about each)
**Dataset properties**
1. **No benign-only day** → no Monday-style tuning; every UNSW run is raw, no suppressions.
2. **Every external host is an attacker** → any "outsider did X" rule scores perfectly but would fail on a
   real network. We classify every rule by its text and built the `test_rule` gate (widen to any → any;
   fail if it fires between internal hosts).
3. **The gate is blind on POP3, SIP, SMB** — no internal host uses them, so rules there can't be checked
   against known-good traffic (only the benign hold-out captures).
4. **Traffic generator (IXIA PerfectStorm) varies every attempt** → rules for one exploit instance fire
   once and never again. Technique-level rules (traversal, XSS, format strings, fuzzing) transfer.
5. **Low signature coverage even for professional rules** — ET Open as shipped catches 9.2%; Generic 7%,
   Analysis 0% even after tuning.
6. **The generator often sends data without the TCP PSH flag** → payload had to be inferred from byte
   counts when measuring what was detectable.

**Ground truth and files**
7. **Ground truth is event-level, not flow-level** → alerts matched by endpoints, ports, protocol and time
   (±2 s); headline counts TCP/UDP only (other protocols have no ports to match).
8. **22 Jan ground truth only covers 11:00–14:00 UTC** → hold-out captures 25 and 50 (picked for spread)
   have no labelled attacks; we used them as a false-alarm check and added captures 3 and 6 (chosen by
   time only) for detection.
9. **Both days number their files from 1** and Wireshark shows Australian time (17 Feb shows as 18 Feb)
   → verified every capture by its first-packet timestamp; hold-out kept in its own folder.
10. **Capture 27 was truncated**; captures are 1–2 GB each and OneDrive downloads stalled (re-downloaded).
11. **10 Snort Community rules don't load** ($SIP_SERVERS undefined) — the same in every run, so harmless,
    but worth knowing.

**Measurement**
12. **Suricata replays are not perfectly repeatable** (thresholds depend on timing) → the old metric counted
    replay noise as gain (hunt: +82 vs +6 real). Now we attribute within one replay.
13. **CIC rules "transferring" to UNSW** rested on two topology-style rules → claim withdrawn.
14. **Suricata decodes URLs** → traversal and encoding rules must use the raw URI buffer (the agent learnt
    this by failing the gate).

**Agent / model**
15. **Reasoning bug:** DeepSeek V4 Pro answers in thinking mode; we discarded that reasoning, so the agent
    lost its plan every turn (100 turns, nothing saved). Fixed; next run finished in 90 turns.
    → The hunt's gain coincides with the fix (confound — stated in the report).
16. **Turn limits and cost**: hunts take 54–143 turns and 3–15 M tokens per capture.
17. **Run-to-run variation**: hunt and hunt2 found largely different attacks (82 shared events) — results
    from one run per capture should not be read as rankings.
18. **What the agent could not do**: DNS high-entropy names need Lua; POP3/SMTP spam needs rate rules the
    gate can't test; DCE/RPC fuzz needs raw byte tests (see report Fig. 5-13).

## 4b. The tools we built so DeepSeek can act as an agent (report Table 3-1, Fig. 3-4)
The model only *proposes* a tool call (JSON); our engine checks it against the profile and runs it.
| Tool | What it does | Safeguard |
|---|---|---|
| count_alerts | alerts per signature | allowlisted paths |
| count_by | count any eve.json field (works on NDJSON) | allowlisted; timeout |
| query_eve_json | jq query over eve.json | 150-line cap |
| read_file / list_directory | read configs, rules, logs | labels, notes, transcripts refused |
| write_file / append_to_file | write rules / propose suppressions | rules/generated/ only; suppressions need approval; hunt: only gate-passed rules |
| run_suricata | replay a capture to validate rules | profile's config only; 10-min timeout |
| search_rules | "is this already covered?" | read-only |
| lookup_vulnerability | local NVD CVE database | offline; refuses dataset terms |
| stack_values | rarest values first (hunting) | hunt profiles |
| test_rule | the anti-topology gate | counts only, never labels |
| suricata_keywords | keywords this Suricata supports | hunt2 only |
- First 8 built for CIC triage; 5 added for UNSW (search_rules, lookup_vulnerability, stack_values, test_rule,
  suricata_keywords). Key lesson: tool design mattered as much as the model (count_by fixed DeepSeek V3;
  test_rule removed topology rules; the reasoning-carry fix made the hunt work).

## 5. Things to show live (≈3 min)
- UI: Profile dropdown → `unsw-v2-hunt2` → its tools. Do not start a run.
- Transcript `triage-2026-10-04-10-03-09-unsw-v2-hunt.txt`: `[THINKING]` plan → `stack_values` rare URLs →
  `test_rule` FAIL → switched to raw URI → PASS → saved.

## 6. Decisions to confirm with him
1. Human-in-the-loop as built: detection rules auto-deploy, suppressions need approval.
2. Split claim as the answer to the research question.
3. Network-based IDS scope (host-based = future work).
4. Is the hunt workflow what he meant by "replicate real engineers"?

## 7. Questions to ask
1. Is the project charter / management plan still required?
2. Is CIC-IDS2017 + UNSW-NB15 acceptable as the dataset choice?
3. Final report format, length and submission date; is a 20-minute presentation OK or should we cut to 15?
4. Should we spend the remaining time on (a) separating the workflow from the bug fix (re-run plain and
   research with the fix), or (b) several runs per capture, or stop experiments and polish the report?

## 8. If he asks
- *Why so low overall?* Low for the human rules too; we measure what AI adds to the strongest human baseline.
- *Could the model see answers?* No — tools only open logs/config/rules/pcaps; hunt hides the attacker range.
- *Is this ML?* No — the model writes Suricata rules; detection stays rule-based and inspectable.
- *Why DeepSeek?* Cost; the provider adapter makes the model swappable (Claude used early on).
