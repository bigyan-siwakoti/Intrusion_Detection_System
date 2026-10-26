# Hunting condition — research notes and scope (4 Oct 2026)

Prompt for this work: the supervisor's advice to look at what real-world detection engineers do and
replicate it with the agent, after the AI rounds on baseline v2 showed ~+0.1 pts genuine (non-topology)
detection gain (PROJECT_STATE §6).

## 1. Diagnosis

The agent is **alert-driven**: the task is "Triage the alerts in X" and the procedure starts at
`count_alerts`. It only investigates traffic some rule already fired on, so it mostly rediscovers rules the
baseline already has; when it reaches further, the easiest pattern is "external host does ordinary protocol
X" (topology). Real detection engineers work from **coverage gaps**, not from alerts.

Two concrete blockers in the code:
- `count_by` (`src/tools.py` `_count_jq_output`) returns `most_common()` first and provider output is capped
  at 8k/15k chars, so the **long tail — the thing a hunter wants — is what gets truncated**.
- The UNSW prompts give the model the attacker range (175.45.176.0/24), which invites topology rules.

## 2. What real detection engineers do (sources)

- **Detection lifecycle**: hypothesis → data source → rule → test against known-bad *and* known-good →
  peer review → deploy → tune. "A CI/CD pipeline … confirming it still fires on the known-bad sample and
  does not light up on the known-good baseline." [Intezer; ReliaQuest]
- **Palantir ADS framework**: every detection is a documented, peer-reviewed artifact with Goal, ATT&CK
  categorisation, Strategy Abstract, Technical Context, **Blind Spots and Assumptions, False Positives,
  Validation**, Priority, Response. → use as the rule-comment template.
  https://blog.palantir.com/alerting-and-detection-strategy-framework-52dc33722df2
- **SpecterOps — Capability Abstraction / Detection Spectrum / Detection in Depth** (Atkinson et al.,
  2020): detect the technique's choke points, not the tool's surface strings; trade precise vs broad
  analytics. Supports "behavioural constraint, not topology".
  https://specterops.io/blog/2020/02/06/capability-abstraction/ ·
  https://specterops.io/blog/2020/02/21/detection-spectrum/ ·
  https://specterops.io/blog/2020/05/08/detection-in-depth/
- **Stacking / least frequency of occurrence**: count each value of a field, inspect the rare ones; "requires
  no machine learning model, no baseline accumulation period" — fits constraint 2.
  https://www.dragos.com/blog/using-neighborhood-keeper-for-long-tail-analysis/

## 3. Closest prior work (LLM → IDS rules)

| Work | What it does | Relevance to us |
|---|---|---|
| RuleAutoPilot (Rehman, Piplai, Kantarcioglu, arXiv 2609.16231, Sep 2026) | Agentic Suricata rules from malware pcaps; benign-traffic fingerprinting first; validation = syntax + fires on source + **quiet on benign corpus**; repair loop | Execution-grounded verification raised F1 0.443 → 0.539. Direct precedent for `test_rule`. Opus 5 backbone 0.656 F1. |
| GRIDAI (Li et al., arXiv 2510.13257, Oct 2025) | Multi-agent: new attack → new rule; variant → repair existing rule; tool-based validation | Precedent for `search_rules` (new vs already covered). |
| FALCON (Mitra et al., arXiv 2508.18684) | CTI → Snort/YARA rules with syntactic, semantic, performance validators | Validator-gate precedent. |
| GenTI (Hadi, Yasmin, Shoker, arXiv 2606.05844, Jun 2026) | Benchmark, 150k Snort/Suricata/ET rules | Context only; abstract-level numbers. |
| "Beyond the Syntax" (di Filippo et al., arXiv 2607.05916, Jul 2026) | 10-expert user study | Experts see LLMs as **drafting/verification aids, not generators**; logic hallucinations in 12% of cases. Supports §3.4 safety asymmetry. |
| Hu et al. (LLM agent, generation + generalisation of IDS rules) | Vulnerability reports + existing rules → rules | Precedent for the research-tool condition. |

**Our difference:** they generate from known-malicious samples or CTI. We start from unlabelled traffic with
no ground truth visible to the model, against a strong human-tuned baseline, and measure genuine
(non-topology) gain.

Signature-IDS floor on UNSW-NB15: INsIDES thesis (UPF, 2017) reports Snort 2.43% detection — **check its
Snort config before citing as comparable**; our ET Open as shipped is 9.2%.
https://repositori.upf.edu/items/ab27cb73-2387-422f-a5d2-e9e93174ae70
(Do NOT cite the "99% TPR / 55.2% FP" figure from the same search — it is not a UNSW result.)

## 4. Pre-scope checks (run 4 Oct, capture 3)

**Single-rule replay time:** `suricata -c config/unsw/baseline.yaml -S one.rules -r 3.pcap` = **18 s**
for a 2 GB capture. No slicing needed for `test_rule`.

**Can an "any-source" rewrite expose topology rules?** Protocol records by subnet, capture 3:

| Protocol | normal clients 59.166 → servers | attacker 175.45 → servers | Test can discriminate? |
|---|---|---|---|
| DNS | 14,502 | 2,632 | yes |
| FTP | 8,581 | 644 | yes |
| HTTP | 6,303 | 1,277 | yes |
| SMTP | 3,005 | 297 | yes |
| SSH | 1,223 | — | yes |
| POP3 | — | 352 | **no** |
| SIP | — | 342 | **no** |
| SMB | — | 321 | **no** |

Demo: `alert smtp any any -> any any (content:"MAIL FROM"; …)` fired **1,668× on normal clients vs 173× on
attacker** → the test flags it as topology. For POP3/SIP/SMB no internal traffic exists, so topology rules
on those protocols stay untestable (existing limitation in PROJECT_STATE stands).

## 5. Scope — condition `unsw-v2-hunt`

Three code changes plus one evaluation hook. Timebox: tools + prompt + one scored round by **~10 Oct**. If it
slips, the hold-out run of frozen v2 + existing rules ships regardless.

1. **`count_by` gets `order: common|rare`** and a header `N distinct values, M total`. Rare mode returns the
   bottom of the distribution. (`src/tools.py`)
2. **New tool `test_rule(rule_text, pcap)`**: writes the rule to a scratch file, `suricata -T` for syntax,
   replays with `-S` against the baseline config, reports alert count and alerts by source/dest *role*
   (HOME_NET-internal vs external) — **twice**: as written, and with addresses rewritten to `any any -> any any`.
   If the `any` version fires on internal→internal traffic, the result says so. Reports counts only,
   never labels. (`src/tools.py`)
3. **Prompt profile `unsw-v2-hunt`** (`src/prompts.py`), ADS-shaped procedure:
   1. Coverage map: event_types present vs alerts per app_proto.
   2. Hunt: stack rare values on *content* fields — http.url / http_user_agent, ftp.command, smtp.mail_from,
      dns.rrname, ssh client software_version, **`anomaly` events** (8,639 in capture 3) — and look for protocol
      activity with no alert on the same flow. **Do not pivot on src_ip/dest_ip** (rediscovers the attacker
      range = topology by another route).
   3. Hypothesis → `search_rules` (already covered?) → write rule with ADS comment (goal, blind spots,
      expected false positives).
   4. `test_rule` must pass before `append_to_file`.
   - Remove the attacker range from this profile's context (decision below).
4. **`src/eval/rounds.py`**: `CONDS` += `"hunt"`; `config/unsw/baseline-hunt.yaml`;
   `rules/generated/unsw/rounds_hunt.rules`; `extra_blocked` hides the plain/research rule files. Same metric:
   genuine (non-topology) TCP/UDP detection, written on 3/1/10, scored on all 6, then hold-out.

## 5b. Built (4 Oct) — and a known gap in the gate

Implemented as scoped; `test_rule` ≈ 20 s per call on a 2 GB capture (both replays in parallel).
Check on capture 3: `MAIL FROM` from outside → FAIL (1,668 internal matches when widened);
`../` in http.uri → PASS (10 alerts, 0 internal).
**Gap:** the gate only catches topology when internal hosts do the same thing. A rule on something only
the attacker does but that is still ordinary (e.g. FTP `MKD`, 2 occurrences, all external) passes. The
rule-class audit (`docs/results/round_rule_classes.json` method) is still needed after scoring.

## 6. Decisions (taken 4 Oct, recorded in CLAUDE.md §3.8)

- **Attacker range in the prompt.** Recommend removing it for `hunt` (a real engineer does not know it).
  Confound: the hunt condition differs from plain/research in two ways; state it.
- **Normal-host test uses dataset documentation** (59.166.0.0/24 is part of HOME_NET in the config). It is
  documented topology, not per-event ground truth. Record in CLAUDE.md §3.8 *before* the run.

## 7. Expected outcome (record before round 1, CLAUDE.md §8)

> Hunt condition adds ≤ +3 genuine points of TCP/UDP detection over baseline v2. Fuzzers, Generic and
> Analysis stay largely undetectable by signature. The `test_rule` gate rejects most topology rules on
> DNS/FTP/HTTP/SMTP/SSH but cannot on POP3/SIP/SMB.

If the result beats this, the gap is the finding; if not, it is a clean answer to the research question.
