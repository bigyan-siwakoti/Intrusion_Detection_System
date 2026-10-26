# Supervisor demo — 5 October 2026 (about 10 minutes)

## Before the meeting
- Start the UI in a terminal with the DeepSeek key exported:
  `cd ~/capstone-ids && PYTHONPATH=. venv/bin/python -m src.server` → open http://localhost:8000
- Have open: the deck (`docs/Group13_Capstone_Presentation.pptx`, Part 2 starts at slide 14; 24 slides),
  the hunt transcript (`triage-2026-10-04-05-48-19-unsw-v2-hunt.txt`) and `rules/generated/unsw/rounds_hunt.rules`.

## 1. The question he asked us (1 min)
"You told us to look at what real engineers do and replicate it with the agent. We did the research
(Palantir ADS, SpecterOps, threat-hunting practice, RuleAutoPilot 2026), built it, ran it, and measured it."

## 2. The baseline first (1 min) — slides 15–16
- ET Open as shipped catches 9.2% of UNSW attack events; re-enabling disabled families chosen by
  service gets 25.7%. Enabling everything gets 31% but 46× the alerts on non-attacker hosts.
- On the untouched 22 Jan hold-out the frozen baseline catches 29.6% — it generalises.

## 3. What we found wrong with our own earlier numbers (2 min) — slide 17
- Earlier AI rounds looked like +11 points. Most of it was topology rules ("an outsider sent mail") —
  only an attack because every external host in UNSW is an attacker.
- Our scoring also counted Suricata replay variance as gain. We now credit only events that the AI rules
  alone caught. Genuine gain is under half a point in every condition.

## 4. Live: the engineer workflow (3 min) — slides 18–19, then the UI
- In the UI: show the **Profile** dropdown next to Model. Pick a UNSW run → only UNSW profiles appear.
  Select `unsw-v2-hunt` → the bar shows its tools (stack_values, test_rule). Do not start a run
  (~12 min, ~5–9M tokens).
- Open the capture-1 hunt transcript (`triage-2026-10-04-10-03-09-unsw-v2-hunt.txt`) and show:
  1. `[THINKING]` blocks — the model's plan, now visible every turn ("First coverage map…").
  2. `stack_values` with `"order":"rare"` on http.url / user-agent → the `/%c0%ae%c0%ae/` traversal.
  3. `test_rule` → FAIL (0 alerts, Suricata decodes the URI) → switched to `http.uri.raw` → PASS → saved.
  4. The final report: rules it dropped (POP3/SIP/SMTP spam too noisy; LDAP string lab-specific).
- Slide 19: MAIL FROM rule fails the gate (1,668 matches between internal hosts); traversal rule passes.

## 5. The bug we found, and the result (3 min) — slides 20–22
- Slide 20: capture 1's first run looped for 100 turns and saved nothing. We debugged it layer by layer:
  DeepSeek V4 Pro was answering in thinking mode and our adapter discarded that reasoning, so the agent
  lost its own plan every turn. One fix; the re-run finished in 90 turns and saved 9 rules.
- Slide 21: 25 hunt rules, 0 topology. Rules written before the fix (capture 3) match one exploit each and
  added 6 events; rules written after it (captures 1, 10) target techniques — traversal, XSS, format
  strings, SMB fuzzing — and added 175. Genuine gain +1.21 pts on the dev captures.
- Slide 22: hold-out (rules frozen first, scored once): hunt +1.53 pts; plain +0.11, research +0.28;
  0 AI-rule alerts on the benign-only captures. The baseline alone: 29.6%.
- Hunt2 (slides 23–25): adding a Suricata keyword reference removed every rule-loading error but gave
  +0.91 / +1.06 pts (dev / hold-out) — runs of the same workflow find different attacks (only 82 shared
  events). ~77% of attacks carried data the baseline could have matched: the gap is unwritten signatures.
- Be upfront: the gain coincides with the bug fix, so "workflow" and "reasoning carried" cannot be
  separated yet — the next run would re-do plain/research with the fix.
- Answer to the research question (split claim): yes for triage with sensor context; for detection,
  triage-driven rules added a fraction of a point, the engineer workflow +1.2–1.5 pts that held on
  unseen traffic — real but modest against the ~70% still missed.

## Questions to ask him
1. Is the project charter / management plan still required?
2. Is CIC-IDS2017 + UNSW-NB15 acceptable as the dataset choice?
3. Does the hunt workflow count as the "replicate real engineers" approach he meant?
4. Confirm: detection rules auto-deploy, suppressions need human approval (our adopted design).
5. Final report format and submission date.

## If asked
- *Why is recall low?* Low for the human-written rules too: ET Open as shipped catches 9.2%, and even the
  tuned baseline misses most events in every category. We measure what the AI adds over the strongest human
  baseline we could build.
- *Could the model see the answers?* No: tools only open logs/config/rules/pcaps; the hunt profile also
  hides the attacker range and other conditions' logs.
- *Why DeepSeek?* Cost; the provider adapter makes the model swappable.
- *What next?* Re-run plain/research with the fix to separate workflow from fix; require technique-level
  rules tested on a second capture.
