# Group 13 — video presentation script (HIT401 Assessment 3, 5–10 minutes)

Due **Sun 11 Oct 2026, 23:59**. Upload to YouTube as **Unlisted** and submit the link on Learnline (unlocks after the Week 9 minutes are submitted).
Deck: `docs/Group13_Video_Presentation.pptx` (13 slides), built by `docs/build_video_deck.js`. Target ≈ 8 min 20 s at ~130 words/min — inside the 5–10 minute window with margin either way.

Recording: PowerPoint → Record → each presenter narrates their own slides; File → Export → Create a Video (1080p). Rehearse once with a timer.

## Slide 1 — BIGYAN (0:00–0:20)  (33 words)

Hi, we are Group 13 — Bigyan, Binay, Irab and Shashwat, supervised by Professor Bharanidharan Shanmugam. Our question: can a large language model replace the human analyst in a rule-based intrusion detection system?

## Slide 2 — BIGYAN (0:20–1:00)  (75 words)

A signature IDS like Suricata only detects what it has rules for. Turning a new attack into a tested rule is manual work — investigate, find what is unique, write, validate, deploy — and it takes scarce expertise. We kept detection rule-based and open-source, with no machine learning: the AI only does the analyst's job around the engine — investigating alerts and authoring rules. And we asked what context it needs to do that well.

## Slide 3 — IRAB (1:00–1:40)  (65 words)

Our literature review covered three areas. Intrusion-detection foundations, from Denning to Snort and NIST's guidance, which show that writing rules is the bottleneck. Recent LLM rule-generation work — GRIDAI, GenTI and RuleAutoPilot — which shows rules must be validated by actually running them. And detection-engineering practice — Palantir's ADS framework, SpecterOps and stack counting — which our supervisor asked us to replicate with the agent.

## Slide 4 — BINAY (1:40–2:25)  (88 words)

Here is our design. Packet captures from two public datasets are replayed through Suricata 8 with the open ET ruleset. Suricata writes eve.json, and our Python triage engine runs an agentic loop over it. A provider adapter means DeepSeek and Claude run the identical loop. The model has two exits: a threat becomes a detection rule, validated by replay and deployed automatically; benign noise becomes a suppression, which needs human approval. A web interface streams every step live, and experiment profiles keep each condition's tools and rules separate.

## Slide 5 — BINAY (2:25–3:05)  (73 words)

The model never touches the system directly. It proposes a tool call, and the engine checks and runs it. Thirteen tools in five groups: investigate, hunt, research, validate and write. The engine enforces the safeguards: an allowlist so the model can never read ground-truth labels, and in the hunt profile a rule is saved only after it passes test_rule — which replays it and rejects any rule that fires on normal internal traffic.

## Slide 6 — IRAB (3:05–3:45)  (94 words)

We scored everything against the datasets' ground-truth labels, never the model's own claims. On CIC-IDS2017 the model identified 13 of 14 attack categories, and 99.4 percent of its rules' alerts on the noisiest days fell on real attacks, against 6.1 percent for the stock rules. On UNSW-NB15, a dataset it had never seen, it found 8 of 9 categories and raised detection from 9.2 to 15.5 percent. And the safety design proved itself: one run wanted to suppress rules that were catching a real Cisco exploit — because suppressions need approval, nothing was blinded.

## Slide 7 — IRAB (3:45–4:25)  (79 words)

Four examples show the model reasoning like an analyst. On the FAKEVERB attack, its first rule caught nothing; it worked out that Suricata's HTTP parser hides non-standard methods and rewrote the rule on raw bytes — 463 alerts. It wrote a rule for a Hulk flood that no stock rule covered. It found the ARES botnet that our own interim report had missed. And its SSH fingerprint rule raised detection from 1 to 28 percent with no false positives.

## Slide 8 — SHASHWAT (4:25–5:00)  (75 words)

The second half of our question asks what context the model needs. We ran the same captures twice — once with everything Suricata logs, once with alerts only. The result surprised us: with alerts alone the model found attacks just as broadly. What context buys is depth. With flows and application data it could say whether an attack succeeded — 52 evidence-backed outcome statements against 9 — and that is what decides an analyst's response.

## Slide 9 — SHASHWAT (5:00–5:35)  (78 words)

The model was not always right, and its mistakes were confident. It deleted two of its own best rules, claiming they were stock rules — they were not. It reported rules as validated that Suricata could not even load. It read ordinary FTP uploads as data theft. On CIC only half its rules ever fired, because our configuration did not load its files — its validation tested nothing. Once the environment was fixed for UNSW, all 18 fired.

## Slide 10 — SHASHWAT (5:35–6:15)  (80 words)

Our supervisor then challenged us to beat a strong human baseline. Re-enabling rule families lifted it to about 25 percent. Against it, the triage rounds looked like 11 points — but most of that was topology: rules that fire on anything from outside, which only works because every outsider in UNSW is an attacker. Counting only what the AI's own real rules caught, plain and research added under half a point. The hunt workflow, copying real detection engineers, added 1.2.

## Slide 11 — BINAY (6:15–6:50)  (81 words)

This is the part that felt most like real engineering. The first hunt on capture 1 ran 100 turns, its rules passed the gate, and it saved nothing. We checked each layer until the raw API showed the cause: DeepSeek was thinking in a separate field our adapter threw away, so every turn it forgot its own plan. One fix, and the rerun finished in 90 turns with 9 rules. Rules written after the fix added 175 events; before it, 6.

## Slide 12 — IRAB (6:50–7:25)  (66 words)

All of this was on development captures, so to check we were not overfitting we froze every rule file and ran a day nobody had looked at, once. The pattern held. The hunt rules gained 1.5 points — slightly more than on the development set — and no AI rule of any condition fired on the benign-only captures. The human baseline generalised too, at 29.5 percent.

## Slide 13 — BIGYAN (7:25–8:20)  (124 words)

So, can an LLM replace the IDS analyst? Our answer is split. Yes for triage: with sensor context the model investigates end to end. Only partly for detection: over a strong human baseline it adds about one and a half points — real, but modest. Our lessons: tools and procedure shape the agent, its reasoning must be carried between turns, and you must measure what the AI alone caught. Next, we would separate the workflow from that fix and test on a live network. Using AI to build this also taught us the same lesson our results show: it speeds up the work enormously, but it needs engineering, checking and a human in the loop. Thank you — we are happy to take questions.

**Total spoken words: 1011 (≈ 7.8 min).** Per presenter: Bigyan 232, Irab 304, Binay 242, Shashwat 233