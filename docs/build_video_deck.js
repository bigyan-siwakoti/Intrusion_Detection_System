// Group 13 — 8-minute video presentation (unit allows 5–10 min) (HIT401 Assessment 3). Spoken script is in the speaker notes and docs/video_script.md.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = "/home/bigyan/capstone-ids";
const RES = path.join(ROOT, "docs/results");
const OUT = path.join(ROOT, "docs/Group13_Video_Presentation.pptx");
const J = (f) => JSON.parse(fs.readFileSync(path.join(RES, f), "utf8"));

// Palette: ink dominates, steel supports, amber is the single accent (matches report figures).
const INK = "0F2533", STEEL = "1F4E79", AMBER = "D9822B", MIST = "EEF3F8", SLATE = "5B6B7A", GREY = "9AA3AD", WHITE = "FFFFFF", RED = "B03A2E";
const HEAD = "Cambria", BODY = "Calibri";

async function icon(Comp, color, size = 256) {
  const svg = renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
  pres.title = "Can an LLM Replace the IDS Analyst? — Group 13";
  const W = 13.333, M = 0.6;

  const IC = {};
  const need = { shield: fa.FaShieldAlt, user: fa.FaUserClock, flask: fa.FaFlask, cogs: fa.FaCogs, search: fa.FaSearch,
    ruler: fa.FaRulerCombined, lock: fa.FaLock, db: fa.FaDatabase, bug: fa.FaBug, robot: fa.FaRobot, check: fa.FaCheckCircle,
    warn: fa.FaExclamationTriangle, bolt: fa.FaBolt, network: fa.FaNetworkWired, eye: fa.FaEye, layers: fa.FaLayerGroup,
    trash: fa.FaTrashAlt, route: fa.FaRoute, question: fa.FaQuestion, users: fa.FaUsers, book: fa.FaBookOpen, chart: fa.FaChartBar };
  for (const [k, C] of Object.entries(need)) IC[k] = await icon(C, WHITE);
  IC.shieldAmber = await icon(fa.FaShieldAlt, AMBER);

  // ---------- helpers ----------
  const title = (s, text, sub) => {
    s.addText(text, { x: M, y: 0.35, w: W - 2 * M, h: 0.8, fontFace: HEAD, fontSize: 34, bold: true, color: INK, margin: 0, isTextBox: true });
    if (sub) s.addText(sub, { x: M, y: 1.1, w: W - 2 * M, h: 0.45, fontFace: BODY, fontSize: 16, color: SLATE, margin: 0, isTextBox: true });
  };
  const badge = (s, key, x, y, d = 0.62, fill = STEEL) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
    s.addImage({ data: IC[key], x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52 });
  };
  const card = (s, x, y, w, h, fill = MIST) =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08 });
  const text = (s, t, o) => s.addText(t, { fontFace: BODY, fontSize: 14, color: INK, margin: 0, valign: "top", isTextBox: true, ...o });
  const bullets = (s, items, o) =>
    s.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: i < items.length - 1 } })),
      { fontFace: BODY, fontSize: 15, color: INK, margin: 0, valign: "top", paraSpaceAfter: 8, isTextBox: true, ...o });
  const stat = (s, big, label, x, y, w, color = AMBER, size = 44) => {
    s.addText(big, { x, y, w, h: 0.85, fontFace: HEAD, fontSize: size, bold: true, color, margin: 0, valign: "bottom", isTextBox: true });
    s.addText(label, { x, y: y + 0.85, w, h: 0.6, fontFace: BODY, fontSize: 13, color: SLATE, margin: 0, valign: "top", isTextBox: true });
  };
  const arrow = (s, x1, y1, x2, y2, color = SLATE, head = true, dash = null) =>
    s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
      flipH: x2 < x1, flipV: y2 < y1,
      line: { color, width: dash ? 1.5 : 2, ...(head ? { endArrowType: "triangle" } : {}), ...(dash ? { dashType: dash } : {}) } });
  const footer = (s, t) => text(s, t, { x: M, y: 7.0, w: W - 2 * M, h: 0.3, fontSize: 10, color: GREY });
  const chartFrame = { catAxisLabelColor: SLATE, valAxisLabelColor: SLATE, catAxisLabelFontFace: BODY, valAxisLabelFontFace: BODY,
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, valGridLine: { color: "E3E7EB", size: 0.75 }, catGridLine: { style: "none" },
    dataLabelFontFace: BODY, dataLabelFontSize: 10, dataLabelColor: INK };
  const R = J("rounds.json");
  const pts = (k, f = "ai_new_genuine") => +(100 * R[k][f] / R[k].tcpudp).toFixed(2);
  const fig = (s, f, x, y, w, h) => s.addImage({ path: path.join(ROOT, "docs/figures", f), x, y, w, h, sizing: { type: "contain", w, h } });
  const who = (s, name, t) => text(s, `${name}  ·  ${t}`, { x: W - M - 3.2, y: 7.0, w: 3.2, h: 0.3, fontSize: 10, color: GREY, align: "right" });

  // ---------- 1. Title ----------
  let s = pres.addSlide(); s.background = { color: INK };
  s.addImage({ data: IC.shieldAmber, x: 10.0, y: 1.5, w: 2.4, h: 2.4 });
  s.addText("Can an LLM replace the IDS analyst?", { x: M, y: 1.4, w: 9, h: 1.7, fontFace: HEAD, fontSize: 44, bold: true, color: WHITE, margin: 0, valign: "top", isTextBox: true });
  s.addText("Generative AI that investigates Suricata alerts and writes detection rules — measured against ground truth",
    { x: M, y: 3.2, w: 8.8, h: 0.9, fontFace: BODY, fontSize: 20, color: AMBER, margin: 0, valign: "top", isTextBox: true });
  s.addText([
    { text: "Group 13  ·  Bigyan Siwakoti  ·  Binay Siwakoti  ·  Irab Baral  ·  Shashwat Acharya", options: { breakLine: true } },
    { text: "Supervisor: Prof. Bharanidharan Shanmugam  ·  HIT401 Capstone Project  ·  Charles Darwin University  ·  October 2026" },
  ], { x: M, y: 5.7, w: W - 2 * M, h: 0.8, fontFace: BODY, fontSize: 15, color: "CADCFC", margin: 0, paraSpaceAfter: 6, isTextBox: true });
  s.addNotes("BIGYAN (0:00–0:20)\nHi, we are Group 13 — Bigyan, Binay, Irab and Shashwat, supervised by Professor Bharanidharan Shanmugam. Our question: can a large language model replace the human analyst in a rule-based intrusion detection system?");

  // ---------- 2. Problem, question, scope ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "No rule, no detection", "A signature IDS is only as good as the rules a human analyst writes for it");
  const steps = ["Investigate", "Find what is unique", "Write rule", "Validate", "Deploy"];
  steps.forEach((t, i) => {
    const x = M + i * 2.45;
    card(s, x, 1.85, 2.1, 0.95, i === 2 ? STEEL : MIST);
    text(s, t, { x, y: 1.85, w: 2.1, h: 0.95, align: "center", valign: "middle", fontSize: 15, bold: true, color: i === 2 ? WHITE : INK });
    if (i < steps.length - 1) arrow(s, x + 2.1, 2.32, x + 2.45, 2.32);
  });
  badge(s, "user", M, 3.0, 0.55, AMBER);
  text(s, "Today a person does every step, for every new attack — hours to days of scarce expertise (Scarfone & Mell 2007)", { x: M + 0.75, y: 3.0, w: 11, h: 0.55, fontSize: 15, color: SLATE, valign: "middle" });
  card(s, M, 3.9, W - 2 * M, 1.35, INK);
  s.addText("Can a large language model take over the analyst’s role — and what context does it need to do that job well?",
    { x: M + 0.4, y: 3.9, w: W - 2 * M - 0.8, h: 1.35, fontFace: HEAD, fontSize: 22, italic: true, color: WHITE, valign: "middle", margin: 0, isTextBox: true });
  const scope = [["lock", "Open-source only"], ["shield", "Rule-based detection, no ML"], ["robot", "AI writes rules, never classifies traffic"], ["network", "Network IDS, offline pcap replay"]];
  scope.forEach(([k, t], i) => {
    const x = M + i * 3.07;
    badge(s, k, x, 5.6, 0.55);
    text(s, t, { x: x + 0.7, y: 5.6, w: 2.3, h: 0.55, fontSize: 13.5, valign: "middle" });
  });
  text(s, "Scope", { x: M, y: 5.3, w: 2, h: 0.3, fontSize: 11, bold: true, color: GREY });
  who(s, "Bigyan", "aim & scope");
  s.addNotes("BIGYAN (0:20–1:00)\nA signature IDS like Suricata only detects what it has rules for. Turning a new attack into a tested rule is manual work — investigate, find what is unique, write, validate, deploy — and it takes scarce expertise. We kept detection rule-based and open-source, with no machine learning: the AI only does the analyst's job around the engine — investigating alerts and authoring rules. And we asked what context it needs to do that well.");

  // ---------- 3. Literature ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "What research and industry practice told us", "38 sources across three themes — each one shaped a design decision");
  const lit = [
    ["book", "Rule-based IDS", "Denning 1987 · Roesch 1999 · Scarfone & Mell 2007 · Sommer & Paxson 2010",
      "Signatures are precise and inspectable; authoring them is the bottleneck. ML detectors are hard to trust in operation."],
    ["robot", "LLMs that write rules", "GRIDAI (Li et al. 2025) · GenTI (Hadi et al. 2026) · RuleAutoPilot (Rehman et al. 2026)",
      "LLMs can draft Suricata rules — but only rules validated by actually running them can be trusted."],
    ["search", "Detection engineering", "Palantir ADS 2017 · SpecterOps (Atkinson 2020) · stack counting (Dragos 2023)",
      "Document every rule, detect the technique not the tool, look at the rarest values first."],
  ];
  lit.forEach(([k, h, src, take], i) => {
    const x = M + i * 4.1;
    card(s, x, 1.85, 3.85, 4.75);
    badge(s, k, x + 0.3, 2.1, 0.7, i === 2 ? AMBER : STEEL);
    text(s, h, { x: x + 1.15, y: 2.12, w: 2.6, h: 0.65, fontFace: HEAD, fontSize: 20, bold: true, valign: "middle" });
    text(s, src, { x: x + 0.3, y: 3.05, w: 3.25, h: 1.1, fontSize: 12.5, color: SLATE, italic: true });
    s.addShape(pres.shapes.LINE, { x: x + 0.3, y: 4.25, w: 3.25, h: 0, line: { color: GREY, width: 0.75 } });
    text(s, take, { x: x + 0.3, y: 4.4, w: 3.25, h: 2.0, fontSize: 15 });
  });
  who(s, "Irab", "literature review");
  s.addNotes("IRAB (1:00–1:40)\nOur literature review covered three areas. Intrusion-detection foundations, from Denning to Snort and NIST's guidance, which show that writing rules is the bottleneck. Recent LLM rule-generation work — GRIDAI, GenTI and RuleAutoPilot — which shows rules must be validated by actually running them. And detection-engineering practice — Palantir's ADS framework, SpecterOps and stack counting — which our supervisor asked us to replicate with the agent.");

  // ---------- 4. Architecture + tech stack ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Design: keep the engine, automate the analyst", "Detection stays deterministic; the model works around it through an agentic loop");
  const box = (t, sub, x, y, w, h, fill = MIST, color = INK) => {
    card(s, x, y, w, h, fill);
    s.addText([{ text: t, options: { bold: true, fontSize: 15, breakLine: !!sub } }, ...(sub ? [{ text: sub, options: { fontSize: 11.5, color: fill === MIST ? SLATE : "D6E2EE" } }] : [])],
      { x, y, w, h, fontFace: BODY, color, align: "center", valign: "middle", margin: 2, isTextBox: true });
  };
  box("pcap captures", "CIC-IDS2017 · UNSW-NB15", 0.6, 1.95, 2.2, 1.0);
  box("Suricata 8.0.6", "ET Open + extra rulesets", 3.2, 1.95, 2.2, 1.0, STEEL, WHITE);
  box("eve.json", "alerts · flows · app-layer", 5.8, 1.95, 2.2, 1.0);
  box("Triage engine", "Python agentic loop + tools", 8.4, 1.95, 2.3, 1.0, AMBER, WHITE);
  box("LLM via adapter", "DeepSeek V4 Pro · Claude", 11.0, 1.95, 1.75, 1.0, INK, WHITE);
  arrow(s, 2.8, 2.45, 3.2, 2.45); arrow(s, 5.4, 2.45, 5.8, 2.45); arrow(s, 8.0, 2.45, 8.4, 2.45);
  arrow(s, 10.7, 2.3, 11.0, 2.3); arrow(s, 11.0, 2.6, 10.7, 2.6);
  // two exits
  arrow(s, 9.55, 2.95, 9.55, 3.45, AMBER);
  box("Threat → detection rule", "validated by replay → auto-deploy", 6.2, 3.5, 3.2, 1.0, MIST);
  box("Benign noise → suppression", "→ human approval required", 9.75, 3.5, 3.0, 1.0, MIST);
  arrow(s, 9.55, 3.45, 7.8, 3.5, AMBER); arrow(s, 9.55, 3.45, 11.25, 3.5, AMBER);
  arrow(s, 6.2, 4.0, 4.3, 4.0, SLATE, true, "dash"); arrow(s, 4.3, 4.0, 4.3, 2.95, SLATE, true, "dash");
  text(s, "new rules loaded into the next replay", { x: 0.6, y: 3.65, w: 3.6, h: 0.6, fontSize: 12, color: SLATE, italic: true, align: "right" });
  box("Web UI (FastAPI + SSE)", "pick dataset, profile & model; watch each step live; export transcript", 0.6, 4.75, 5.4, 0.85);
  box("Experiment profiles", "tools, prompt, config & rule file fixed per condition", 6.2, 4.75, 6.55, 0.85);
  text(s, "Tech stack", { x: M, y: 5.85, w: 2, h: 0.3, fontSize: 11, bold: true, color: GREY });
  const stack = ["Suricata 8.0.6", "ET Open", "Python 3.12", "FastAPI", "jq", "tshark", "DeepSeek V4 Pro", "Claude", "Ubuntu (WSL)"];
  let sx = M;
  stack.forEach((t) => { const w = 0.3 + t.length * 0.105; card(s, sx, 6.2, w, 0.42, MIST); text(s, t, { x: sx, y: 6.2, w, h: 0.42, fontSize: 12, align: "center", valign: "middle" }); sx += w + 0.15; });
  who(s, "Binay", "design");
  s.addNotes("BINAY (1:40–2:25)\nHere is our design. Packet captures from two public datasets are replayed through Suricata 8 with the open ET ruleset. Suricata writes eve.json, and our Python triage engine runs an agentic loop over it. A provider adapter means DeepSeek and Claude run the identical loop. The model has two exits: a threat becomes a detection rule, validated by replay and deployed automatically; benign noise becomes a suppression, which needs human approval. A web interface streams every step live, and experiment profiles keep each condition's tools and rules separate.");

  // ---------- 5. Tools ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "The agent’s tools: it proposes, the engine runs", "13 tools in five groups; each experiment profile switches on only the ones it needs");
  fig(s, "_video_tools_crop.png", 0.9, 1.65, 11.5, 5.25);
  who(s, "Binay", "tools");
  s.addNotes("BINAY (2:25–3:05)\nThe model never touches the system directly. It proposes a tool call, and the engine checks and runs it. Thirteen tools in five groups: investigate, hunt, research, validate and write. The engine enforces the safeguards: an allowlist so the model can never read ground-truth labels, and in the hunt profile a rule is saved only after it passes test_rule — which replays it and rejects any rule that fires on normal internal traffic.");

  // ---------- 6. Results part 1 ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Results: triage works on two datasets", "Every number scored against the datasets’ ground-truth labels — not the model’s own claims");
  card(s, M, 1.8, 5.9, 3.3); card(s, M + 6.23, 1.8, 5.9, 3.3);
  text(s, "CIC-IDS2017 (development)", { x: M + 0.3, y: 1.95, w: 5.4, h: 0.45, fontFace: HEAD, fontSize: 18, bold: true });
  stat(s, "13 / 14", "attack categories identified by the model", M + 0.3, 2.45, 2.7);
  stat(s, "99.4%", "of AI-rule alerts on noisy days fell on real attacks (stock rules: 6.1%)", M + 3.1, 2.45, 2.6);
  text(s, "UNSW-NB15 (never seen before)", { x: M + 6.53, y: 1.95, w: 5.4, h: 0.45, fontFace: HEAD, fontSize: 18, bold: true });
  stat(s, "8 / 9", "attack categories identified", M + 6.53, 2.45, 2.4);
  stat(s, "9.2 → 15.5%", "event detection, stock ET Open → + AI rules", M + 9.0, 2.45, 3.0, AMBER, 36);
  card(s, M, 5.35, W - 2 * M, 1.4, INK);
  badge(s, "lock", M + 0.3, 5.75, 0.6, AMBER);
  s.addText([{ text: "The safety design worked.  ", options: { bold: true, color: AMBER } },
             { text: "One UNSW run proposed suppressing two rules as false positives — they were catching a real Cisco exploit. Suppressions need human approval, so the sensor was never blinded.", options: { color: WHITE } }],
    { x: M + 1.15, y: 5.35, w: W - 2 * M - 1.4, h: 1.4, fontFace: BODY, fontSize: 16, valign: "middle", margin: 0, isTextBox: true });
  who(s, "Irab", "results");
  s.addNotes("IRAB (3:05–3:45)\nWe scored everything against the datasets' ground-truth labels, never the model's own claims. On CIC-IDS2017 the model identified 13 of 14 attack categories, and 99.4 percent of its rules' alerts on the noisiest days fell on real attacks, against 6.1 percent for the stock rules. On UNSW-NB15, a dataset it had never seen, it found 8 of 9 categories and raised detection from 9.2 to 15.5 percent. And the safety design proved itself: one run wanted to suppress rules that were catching a real Cisco exploit — because suppressions need approval, nothing was blinded.");

  // ---------- 7. Stories: what stock rules missed ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "What the AI caught that 52,000 stock rules missed", "Four examples from CIC-IDS2017 — each confirmed against the ground-truth labels");
  const stories = [
    ["bug", "FAKEVERB DoS", "Worked out that Suricata’s HTTP parser hides non-standard methods, and rewrote its rule on the raw payload", "0 → 463 alerts"],
    ["bolt", "Hulk HTTP flood", "A 149,703-request cache-busting flood with no dedicated stock rule — the AI wrote and validated one", "new detection"],
    ["network", "ARES botnet", "Five infected hosts polling a C2 server; listed as undetected in our interim report, found later by the model", "15 / 15 alerts on Bot flows"],
    ["lock", "SSH brute force", "A client-fingerprint rule for the Paramiko toolkit, with no false positives", "1.0% → 28.4% of flows"],
  ];
  stories.forEach(([k, h, d, n], i) => {
    const x = M + (i % 2) * 6.18, y = 1.8 + Math.floor(i / 2) * 2.55;
    card(s, x, y, 5.95, 2.3);
    badge(s, k, x + 0.3, y + 0.3, 0.6, i % 3 === 0 ? AMBER : STEEL);
    text(s, h, { x: x + 1.1, y: y + 0.3, w: 4.6, h: 0.6, fontFace: HEAD, fontSize: 19, bold: true, valign: "middle" });
    text(s, d, { x: x + 0.3, y: y + 1.0, w: 3.6, h: 1.2, fontSize: 13.5 });
    text(s, n, { x: x + 3.95, y: y + 1.0, w: 1.8, h: 1.1, fontFace: HEAD, fontSize: 17, bold: true, color: AMBER, align: "right", valign: "middle" });
  });
  who(s, "Irab", "results");
  s.addNotes("IRAB (3:45–4:25)\nFour examples show the model reasoning like an analyst. On the FAKEVERB attack, its first rule caught nothing; it worked out that Suricata's HTTP parser hides non-standard methods and rewrote the rule on raw bytes — 463 alerts. It wrote a rule for a Hulk flood that no stock rule covered. It found the ARES botnet that our own interim report had missed. And its SSH fingerprint rule raised detection from 1 to 28 percent with no false positives.");

  // ---------- 8. Experiment 1: context ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Experiment 1: what context does the model need?", "Same captures (UNSW 1, 3, 10): full sensor context versus alert events only");
  fig(s, "fig5-6_experiment1.png", M, 1.75, 8.2, 4.6);
  card(s, 9.1, 1.85, 3.63, 2.25, MIST);
  text(s, "Breadth without context", { x: 9.3, y: 1.98, w: 3.3, h: 0.45, fontFace: HEAD, fontSize: 16, bold: true });
  text(s, "Alerts alone were enough to spot the attacks — 7 categories vs 6.", { x: 9.3, y: 2.45, w: 3.3, h: 1.5, fontSize: 13.5 });
  card(s, 9.1, 4.3, 3.63, 2.45, INK);
  text(s, "Depth with it", { x: 9.3, y: 4.43, w: 3.3, h: 0.45, fontFace: HEAD, fontSize: 16, bold: true, color: AMBER });
  text(s, "Only full context showed whether attacks succeeded: 52 evidence-backed outcome statements vs 9.", { x: 9.3, y: 4.9, w: 3.3, h: 1.75, fontSize: 13.5, color: WHITE });
  who(s, "Shashwat", "Experiment 1");
  s.addNotes("SHASHWAT (4:25–5:00)\nThe second half of our question asks what context the model needs. We ran the same captures twice — once with everything Suricata logs, once with alerts only. The result surprised us: with alerts alone the model found attacks just as broadly. What context buys is depth. With flows and application data it could say whether an attack succeeded — 52 evidence-backed outcome statements against 9 — and that is what decides an analyst's response.");

  // ---------- 9. Confident errors ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "But its errors were confident", "Why the model cannot be left unsupervised — every error below was reported as a success");
  const errs = [
    ["trash", "Deleted two of its best rules", "claiming they were stock ET rules — they were not (a hallucinated fact)"],
    ["warn", "Rules that never work", "3 rules Suricata rejects, 1 that can never fire — reported as validated"],
    ["eye", "Misread normal traffic", "routine FTP uploads from every workstation reported as data exfiltration"],
    ["question", "Opposite verdicts", "same evidence, different runs: 5 said true positive, 1 said suppress"],
  ];
  errs.forEach(([k, h, d], i) => {
    const y = 1.8 + i * 1.0;
    badge(s, k, M, y + 0.1, 0.6, i === 0 ? RED : STEEL);
    text(s, h, { x: M + 0.8, y, w: 3.6, h: 0.8, fontFace: HEAD, fontSize: 17, bold: true, valign: "middle" });
    text(s, d, { x: M + 4.4, y, w: 3.6, h: 0.8, fontSize: 13.5, valign: "middle", color: SLATE });
  });
  card(s, 8.9, 1.8, 3.83, 3.9, MIST);
  stat(s, "16 / 32", "CIC rules that actually fired on replay — the configuration loaded only 3 of 10 rule files", 9.15, 1.95, 3.4, RED, 40);
  stat(s, "18 / 18", "UNSW rules that fired, once the configuration loaded the model’s file", 9.15, 3.75, 3.4, STEEL, 40);
  text(s, "An agent’s self-validation is only as good as its environment.", { x: M, y: 6.1, w: W - 2 * M, h: 0.5, fontSize: 16, italic: true, color: INK });
  who(s, "Shashwat", "model errors");
  s.addNotes("SHASHWAT (5:00–5:35)\nThe model was not always right, and its mistakes were confident. It deleted two of its own best rules, claiming they were stock rules — they were not. It reported rules as validated that Suricata could not even load. It read ordinary FTP uploads as data theft. On CIC only half its rules ever fired, because our configuration did not load its files — its validation tested nothing. Once the environment was fixed for UNSW, all 18 fired.");

  // ---------- 10. Strong baseline: topology trap + hunt ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Against a strong baseline: what did the AI alone catch?", "UNSW baseline v2 (re-enabled rule families) detects ~25% — the bar the AI now has to clear");
  const cats = ["Plain", "Research", "Hunt", "Hunt2"];
  const ks = ["plain-r2", "research-r2", "hunt-r1", "hunt2-r1"];
  s.addChart(pres.charts.BAR, [
    { name: "Looked like (AI-rule alerts incl. topology rules)", labels: cats, values: ks.map((k) => pts(k, "ai_new")) },
    { name: "Genuine (signature + behaviour rules only)", labels: cats, values: ks.map((k) => pts(k)) },
  ], { x: M, y: 1.75, w: 7.6, h: 5.0, barDir: "col", barGrouping: "clustered", chartColors: ["C9D3DD", AMBER],
       showValue: true, dataLabelFormatCode: "+0.0#", valAxisTitle: "detection gain (points, 6 dev captures)", showValAxisTitle: true,
       valAxisTitleFontSize: 11, valAxisTitleColor: SLATE, showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: BODY, ...chartFrame });
  card(s, 8.6, 1.85, 4.13, 2.35);
  text(s, "The topology trap", { x: 8.85, y: 1.98, w: 3.7, h: 0.4, fontFace: HEAD, fontSize: 17, bold: true });
  text(s, "“Outside host sends mail” fires on every attacker — only because in UNSW every external host is one. Not a real detection.", { x: 8.85, y: 2.42, w: 3.7, h: 1.7, fontSize: 13.5 });
  card(s, 8.6, 4.4, 4.13, 2.35, INK);
  text(s, "Hunt = a detection engineer’s workflow", { x: 8.85, y: 4.53, w: 3.7, h: 0.5, fontFace: HEAD, fontSize: 16, bold: true, color: AMBER });
  text(s, "Stack rare values → write a technique rule → must pass the anti-topology gate. 25 rules, 0 topology, 0 alerts on normal hosts.", { x: 8.85, y: 5.05, w: 3.7, h: 1.6, fontSize: 13.5, color: WHITE });
  who(s, "Shashwat", "analysis");
  s.addNotes("SHASHWAT (5:35–6:15)\nOur supervisor then challenged us to beat a strong human baseline. Re-enabling rule families lifted it to about 25 percent. Against it, the triage rounds looked like 11 points — but most of that was topology: rules that fire on anything from outside, which only works because every outsider in UNSW is an attacker. Counting only what the AI's own real rules caught, plain and research added under half a point. The hunt workflow, copying real detection engineers, added 1.2.");

  // ---------- 11. The bug ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "We found a bug by watching the agent fail", "Hunt, capture 1, first attempt: rules passed the gate — and nothing was saved");
  const steps2 = [["warn", "Symptom", "100 turns, 8.4 M tokens. It re-tested rules that had already passed and never saved one. The UI showed tool calls but no reasoning."],
                  ["search", "Diagnosis", "Checked each layer — engine, server, browser, raw API. DeepSeek V4 Pro answered in thinking mode; its reasoning came back in a field our adapter ignored."],
                  ["check", "Fix", "Carry the reasoning back every turn. The model kept its own plan: capture 1 finished in 90 turns and saved 9 rules."]];
  steps2.forEach(([k, h, d], i) => {
    const x = M + i * 4.1;
    card(s, x, 1.85, 3.85, 3.6, i === 2 ? INK : MIST);
    badge(s, k, x + 0.3, 2.1, 0.62, i === 2 ? AMBER : STEEL);
    text(s, h, { x: x + 1.1, y: 2.12, w: 2.6, h: 0.6, fontFace: HEAD, fontSize: 20, bold: true, valign: "middle", color: i === 2 ? AMBER : INK });
    text(s, d, { x: x + 0.3, y: 2.95, w: 3.3, h: 2.4, fontSize: 14, color: i === 2 ? WHITE : INK });
    if (i < 2) arrow(s, x + 3.85, 3.65, x + 4.1, 3.65, AMBER);
  });
  stat(s, "6 → 175", "attack events added by hunt rules written before vs after the fix — instance rules became technique rules", M, 5.6, 7.5, AMBER, 34);
  who(s, "Binay", "debugging");
  s.addNotes("BINAY (6:15–6:50)\nThis is the part that felt most like real engineering. The first hunt on capture 1 ran 100 turns, its rules passed the gate, and it saved nothing. We checked each layer until the raw API showed the cause: DeepSeek was thinking in a separate field our adapter threw away, so every turn it forgot its own plan. One fix, and the rerun finished in 90 turns with 9 rules. Rules written after the fix added 175 events; before it, 6.");

  // ---------- 12. Hold-out ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Hold-out: rules frozen, unseen traffic, scored once", "UNSW 22 Jan 2015 — a day nobody looked at while building or tuning");
  s.addChart(pres.charts.BAR, [
    { name: "Development captures", labels: cats, values: ks.map((k) => pts(k)) },
    { name: "Hold-out (unseen)", labels: cats, values: ["plain-r2-holdout", "research-r2-holdout", "hunt-r1-holdout", "hunt2-r1-holdout"].map((k) => pts(k)) },
  ], { x: M, y: 1.75, w: 7.6, h: 5.0, barDir: "col", barGrouping: "clustered", chartColors: [STEEL, AMBER],
       showValue: true, dataLabelFormatCode: "+0.00", valAxisTitle: "genuine detection gain (points)", showValAxisTitle: true,
       valAxisTitleFontSize: 11, valAxisTitleColor: SLATE, showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: BODY, ...chartFrame });
  stat(s, "+" + pts("hunt-r1-holdout").toFixed(2) + " pts", "hunt rules on unseen traffic — the gain held, and grew", 8.7, 1.9, 4.0);
  stat(s, "0", "AI-rule alerts on the benign-only hold-out captures, in every condition", 8.7, 3.55, 4.0, STEEL);
  stat(s, (100 * R["baseline-holdout"].base_det / R["baseline-holdout"].tcpudp).toFixed(1) + "%", "caught by the frozen human baseline alone", 8.7, 5.2, 4.0, SLATE);
  who(s, "Irab", "validation");
  s.addNotes("IRAB (6:50–7:25)\nAll of this was on development captures, so to check we were not overfitting we froze every rule file and ran a day nobody had looked at, once. The pattern held. The hunt rules gained 1.5 points — slightly more than on the development set — and no AI rule of any condition fired on the benign-only captures. The human baseline generalised too, at 29.5 percent.");

  // ---------- 13. Conclusion & reflection ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Answer: a split claim", "What we found, what we learned, what comes next");
  card(s, M, 1.75, 5.95, 2.1, STEEL);
  text(s, "Yes — for triage", { x: M + 0.3, y: 1.9, w: 5.4, h: 0.5, fontFace: HEAD, fontSize: 20, bold: true, color: WHITE });
  text(s, "With sensor context the model investigates end to end: 13/14 and 8/9 attack categories identified, and it can tell whether an attack succeeded.", { x: M + 0.3, y: 2.45, w: 5.4, h: 1.3, fontSize: 14.5, color: WHITE });
  card(s, M + 6.18, 1.75, 5.95, 2.1, AMBER);
  text(s, "Partly — for detection", { x: M + 6.48, y: 1.9, w: 5.4, h: 0.5, fontFace: HEAD, fontSize: 20, bold: true, color: WHITE });
  text(s, "Over a strong human baseline the engineer workflow adds +1.2 to +1.5 points with no false alarms — real, but modest.", { x: M + 6.48, y: 2.45, w: 5.4, h: 1.3, fontSize: 14.5, color: WHITE });
  text(s, "Lessons learned", { x: M, y: 4.1, w: 6, h: 0.4, fontFace: HEAD, fontSize: 17, bold: true });
  bullets(s, ["Tools and procedure shape the agent more than the prompt", "Carry the model’s reasoning between turns — dropping it made the agent loop", "Measure what the AI alone caught: our early +11 points were mostly an artefact"],
    { x: M, y: 4.55, w: 6.6, h: 2.2, fontSize: 14 });
  text(s, "Next steps", { x: M + 7.0, y: 4.1, w: 5, h: 0.4, fontFace: HEAD, fontSize: 17, bold: true });
  bullets(s, ["Separate the hunt workflow from the reasoning fix", "Several runs per capture — runs find different attacks", "Live network and host-based sensors"],
    { x: M + 7.0, y: 4.55, w: 5.1, h: 2.2, fontSize: 14 });
  who(s, "Bigyan", "conclusion");
  s.addNotes("BIGYAN (7:25–8:20)\nSo, can an LLM replace the IDS analyst? Our answer is split. Yes for triage: with sensor context the model investigates end to end. Only partly for detection: over a strong human baseline it adds about one and a half points — real, but modest. Our lessons: tools and procedure shape the agent, its reasoning must be carried between turns, and you must measure what the AI alone caught. Next, we would separate the workflow from that fix and test on a live network. Using AI to build this also taught us the same lesson our results show: it speeds up the work enormously, but it needs engineering, checking and a human in the loop. Thank you — we are happy to take questions.");

  await pres.writeFile({ fileName: OUT });
  console.log("wrote", OUT);
})();
