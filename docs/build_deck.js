// Group 13 capstone presentation (15 min). Numbers are read from docs/results/*.json.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = "/home/bigyan/capstone-ids";
const RES = path.join(ROOT, "docs/results");
const OUT = path.join(ROOT, "docs/Group13_Capstone_Presentation.pptx");
const J = (f) => JSON.parse(fs.readFileSync(path.join(RES, f), "utf8"));
const unsw = J("unsw_scores.json");
const exp1 = J("experiment1.json");

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

  // ---------- 1. Title ----------
  let s = pres.addSlide(); s.background = { color: INK };
  s.addImage({ data: IC.shieldAmber, x: 9.9, y: 1.4, w: 2.6, h: 2.6 });
  s.addText("Can an LLM replace the IDS analyst?", { x: M, y: 1.35, w: 8.9, h: 1.7, fontFace: HEAD, fontSize: 44, bold: true, color: WHITE, margin: 0, valign: "top", isTextBox: true });
  s.addText("Automated generation of intrusion detection rules using generative AI in a rule-based IDS deployment",
    { x: M, y: 3.15, w: 8.6, h: 0.9, fontFace: BODY, fontSize: 20, color: AMBER, margin: 0, valign: "top", isTextBox: true });
  s.addText([
    { text: "Group 13  ·  Bigyan Siwakoti  ·  Binay Siwakoti  ·  Irab Baral  ·  Shashwat Acharya", options: { breakLine: true } },
    { text: "Supervisor: Prof. Bharanidharan Shanmugam  ·  Charles Darwin University  ·  October 2026" },
  ], { x: M, y: 5.6, w: W - 2 * M, h: 0.8, fontFace: BODY, fontSize: 15, color: "CADCFC", margin: 0, paraSpaceAfter: 6, isTextBox: true });
  s.addNotes("PRESENTER: Bigyan (≈0:30). Introduce the team and the question in one sentence: we tested whether a large language model can do the job of the analyst who sits between an intrusion detection system and its rules — investigating alerts and writing new detection rules — without replacing the rule-based engine itself.");

  // ---------- 2. Problem ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Detection is only as good as its rules", "Signature-based IDS: deterministic and inspectable, but blind to anything without a rule");
  bullets(s, [
    "No rule, no detection — however capable the engine",
    "Turning an observed attack into a tested rule is manual work: investigate, identify invariants, write, validate, deploy",
    "Scarfone & Mell (NIST SP 800-94) describe this cycle as taking hours to days of scarce expertise",
  ], { x: M, y: 1.9, w: 5.6, h: 3.2 });
  const steps = ["Investigate", "Identify", "Write rule", "Validate", "Deploy"];
  steps.forEach((t, i) => {
    const x = 6.65 + i * 1.24;
    card(s, x, 2.15, 1.08, 1.0, i === 2 ? STEEL : MIST);
    text(s, t, { x, y: 2.15, w: 1.08, h: 1.0, align: "center", valign: "middle", fontSize: 11.5, bold: true, color: i === 2 ? WHITE : INK });
    if (i < steps.length - 1) arrow(s, x + 1.08, 2.65, x + 1.24, 2.65);
  });
  badge(s, "user", 6.65, 3.55, 0.62, AMBER);
  text(s, "Today a human analyst performs every step, for every new attack", { x: 7.4, y: 3.6, w: 5.2, h: 0.6, fontSize: 14, color: SLATE, valign: "middle" });
  card(s, M, 5.25, W - 2 * M, 1.25, INK);
  s.addText([{ text: "52,647", options: { fontFace: HEAD, fontSize: 36, bold: true, color: AMBER } },
             { text: "   community rules in ET Open, and still whole attack categories went undetected", options: { fontFace: BODY, fontSize: 15, color: WHITE } }],
    { x: M + 0.4, y: 5.25, w: W - 2 * M - 0.8, h: 1.25, valign: "middle", margin: 0, isTextBox: true });
  s.addNotes("PRESENTER: Bigyan (≈0:50). The bottleneck is not the detection engine, it is the human loop around it. Emphasise that we keep detection rule-based and inspectable on purpose — the supervisor's constraint was no machine-learning detector. The AI's job is to do the analyst's work: investigate and author rules the engine then evaluates.");

  // ---------- 3. Research question ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Research question");
  card(s, M, 1.35, W - 2 * M, 1.45, MIST);
  s.addText("Can a large language model take over the analyst's role in the alert-handling loop of a rule-based IDS — and what context does it need to do that job well?",
    { x: M + 0.4, y: 1.35, w: W - 2 * M - 0.8, h: 1.45, fontFace: HEAD, fontSize: 22, italic: true, color: INK, valign: "middle", margin: 0, isTextBox: true });
  const aims = [
    ["cogs", "Build", "An agentic triage engine that investigates Suricata alerts, writes detection rules and validates them by replay"],
    ["ruler", "Measure", "Every AI-authored rule against ground-truth labels, on two datasets — one the system was never tuned for"],
    ["flask", "Test context", "Experiment 1: triage with alert events only versus full sensor context"],
  ];
  aims.forEach(([k, h, d], i) => {
    const x = M + i * 4.1;
    card(s, x, 3.15, 3.85, 2.6);
    badge(s, k, x + 0.3, 3.4);
    text(s, h, { x: x + 1.1, y: 3.45, w: 2.5, h: 0.5, fontFace: HEAD, fontSize: 20, bold: true, valign: "middle" });
    text(s, d, { x: x + 0.3, y: 4.25, w: 3.25, h: 1.4, fontSize: 14 });
  });
  text(s, "Constraints: open-source only  ·  no machine-learning detection  ·  the model authors rules, it never classifies traffic",
    { x: M, y: 6.15, w: W - 2 * M, h: 0.4, fontSize: 14, color: SLATE });
  s.addNotes("PRESENTER: Bigyan (≈0:45). Read the question, then the three aims. Stress the second half of the question — 'what context does it need' — because Experiment 1 answers it later.");

  // ---------- 4. Approach ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Keep the engine, automate the analyst", "Three stages — detection stays deterministic, the model works around it");
  const stages = [
    ["shield", "1  Detection", ["Suricata 8.0.6 replays pcap files", "ET Open ruleset, 52,647 rules", "Benign Monday baseline: 80 documented suppressions → 0 alerts"]],
    ["robot", "2  Triage", ["LLM agent investigates eve.json", "Six-step procedure: big picture → categorise → investigate → deep-dive → act → report", "8 tools, no free shell access"]],
    ["check", "3  Output", ["Threat → write rule → validate by replay → auto-deploy", "Benign noise → propose suppression → human approval"]],
  ];
  stages.forEach(([k, h, items], i) => {
    const x = M + i * 4.15;
    card(s, x, 1.95, 3.75, 4.3);
    badge(s, k, x + 0.3, 2.2, 0.7, i === 1 ? AMBER : STEEL);
    text(s, h, { x: x + 1.2, y: 2.25, w: 2.4, h: 0.6, fontFace: HEAD, fontSize: 21, bold: true, valign: "middle" });
    bullets(s, items, { x: x + 0.3, y: 3.15, w: 3.2, h: 2.9, fontSize: 14 });
    if (i < 2) arrow(s, x + 3.75, 4.1, x + 4.15, 4.1, AMBER);
  });
  footer(s, "Design decisions: alert-only rules (a Suricata 'pass' rule would stop inspecting the whole flow); offline pcap replay; all tuning in threshold.config");
  s.addNotes("PRESENTER: Bigyan (≈0:50). Walk left to right. Detection: stock community rules plus a baseline built on the benign Monday capture, like a real SOC would tune a sensor. Triage: the model does the analyst's investigation. Output: two exits — detection rules deploy automatically, suppressions need a human (explained shortly). Hand over to Binay for how the system is built.");

  // ---------- 5. Tech stack & architecture ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Tech stack and architecture");
  const box = (x, y, w, h, t, fill = MIST, color = INK, bold = true) => {
    card(s, x, y, w, h, fill);
    text(s, t, { x, y, w, h, align: "center", valign: "middle", fontSize: 13, bold, color });
  };
  box(M, 1.7, 1.9, 0.9, "pcap captures\nCIC-IDS2017 · UNSW-NB15");
  box(3.0, 1.7, 1.9, 0.9, "Suricata 8.0.6\n+ ET Open + AI rules", STEEL, WHITE);
  box(5.4, 1.7, 1.9, 0.9, "eve.json (NDJSON)\nalerts · flows · app-layer");
  box(5.4, 3.35, 1.9, 1.1, "Triage engine\n(Python, agentic loop)", AMBER, WHITE);
  box(2.6, 3.35, 2.3, 1.1, "Provider adapter\nidentical prompt + tools");
  box(M, 5.0, 1.9, 0.75, "Claude Opus 5", STEEL, WHITE);
  box(2.75, 5.0, 1.9, 0.75, "DeepSeek V3 / V4 Pro", STEEL, WHITE);
  box(5.4, 5.25, 1.9, 0.95, "rules/generated/\nreplay-validated");
  box(7.9, 3.35, 1.8, 1.1, "Web UI\nFastAPI + SSE stream");
  arrow(s, 2.5, 2.15, 3.0, 2.15); arrow(s, 4.9, 2.15, 5.4, 2.15); arrow(s, 6.35, 2.6, 6.35, 3.35);
  arrow(s, 5.4, 3.9, 4.9, 3.9); arrow(s, 3.2, 4.45, 1.55, 5.0); arrow(s, 3.75, 4.45, 3.7, 5.0);
  arrow(s, 6.35, 4.45, 6.35, 5.25); arrow(s, 7.3, 3.9, 7.9, 3.9);
  arrow(s, 7.3, 5.72, 7.65, 5.72, SLATE, false, "dash"); arrow(s, 7.65, 5.72, 7.65, 1.42, SLATE, false, "dash");
  arrow(s, 7.65, 1.42, 3.95, 1.42, SLATE, false, "dash"); arrow(s, 3.95, 1.42, 3.95, 1.7, SLATE, true, "dash");
  text(s, "new rules are loaded into the next replay", { x: 4.3, y: 1.17, w: 3.3, h: 0.24, fontSize: 10, color: SLATE, italic: true });
  card(s, 10.1, 1.7, 2.63, 4.5, INK);
  text(s, "Stack", { x: 10.35, y: 1.85, w: 2.2, h: 0.45, fontFace: HEAD, fontSize: 18, bold: true, color: AMBER });
  s.addText(["Suricata 8.0.6 (IDS engine)", "ET Open ruleset", "jq over NDJSON", "Python 3 triage engine", "Anthropic + DeepSeek APIs", "FastAPI + Server-Sent Events", "Ubuntu on WSL"]
    .map((t, i, a) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < a.length - 1 } })),
    { x: 10.35, y: 2.4, w: 2.25, h: 3.6, fontFace: BODY, fontSize: 13, color: WHITE, margin: 0, paraSpaceAfter: 6, valign: "top", isTextBox: true });
  s.addNotes("PRESENTER: Binay (≈1:00). Follow the arrows: pcap → Suricata → eve.json → triage engine. The provider adapter lets Claude and DeepSeek run the identical loop with identical tools, so models can be swapped. Rules the model writes go to rules/generated and are loaded into the next Suricata replay (dashed line) — that is how the model validates its own rules. The web UI streams every tool call live.");

  // ---------- 6. Agentic capability ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Giving the model agentic capability", "A tool-calling loop: the model chooses actions, the engine executes them through validated tools");
  const loop = [["1", "Engine sends history + tool schemas", 0.7, 2.05], ["2", "Model replies with a tool call (JSON)", 3.4, 2.05],
                ["3", "Engine validates path and executes", 3.4, 4.25], ["4", "Result appended; model reads it and decides next step", 0.7, 4.25]];
  loop.forEach(([n, t, x, y], i) => {
    card(s, x, y, 2.35, 1.55, i === 1 ? STEEL : MIST);
    text(s, n, { x: x + 0.2, y: y + 0.12, w: 0.5, h: 0.45, fontFace: HEAD, fontSize: 22, bold: true, color: i === 1 ? AMBER : AMBER });
    text(s, t, { x: x + 0.2, y: y + 0.55, w: 1.95, h: 0.95, fontSize: 13, color: i === 1 ? WHITE : INK });
  });
  arrow(s, 3.05, 2.8, 3.4, 2.8, AMBER); arrow(s, 4.57, 3.6, 4.57, 4.25, AMBER); arrow(s, 3.4, 5.0, 3.05, 5.0, AMBER); arrow(s, 1.87, 4.25, 1.87, 3.6, AMBER);
  text(s, "repeats until the model answers without a tool call (max 100 turns)", { x: 0.7, y: 5.95, w: 5.05, h: 0.55, fontSize: 12, color: SLATE, italic: true });
  const tools = [["count_alerts", "alerts per signature"], ["count_by", "aggregate any field"], ["query_eve_json", "jq query, capped output"], ["read_file", "configs, rules, logs"],
                 ["write_file", "rules/generated only"], ["append_to_file", "rules/generated only"], ["run_suricata", "replay pcap to validate"], ["list_directory", "allowlisted folders"]];
  tools.forEach(([n, d], i) => {
    const x = 6.35 + (i % 2) * 3.2, y = 1.85 + Math.floor(i / 2) * 1.02;
    card(s, x, y, 3.0, 0.85);
    text(s, n, { x: x + 0.2, y: y + 0.08, w: 2.7, h: 0.38, fontSize: 14, bold: true, fontFace: "Courier New", color: STEEL });
    text(s, d, { x: x + 0.2, y: y + 0.45, w: 2.7, h: 0.35, fontSize: 12, color: SLATE });
  });
  card(s, 6.35, 6.0, 6.2, 0.75, INK);
  text(s, "Tool design mattered as much as the model: DeepSeek V3 failed every run until we added count_by", { x: 6.55, y: 6.0, w: 5.85, h: 0.75, fontSize: 13, color: WHITE, valign: "middle" });
  s.addNotes("PRESENTER: Binay (≈1:05). A hosted model can only produce text. The loop turns it into an agent: each turn it can request one of eight tools; our engine checks the request (paths are allowlisted, writes only into rules/generated) and returns the result. The model decides what to investigate and in what order. Key lesson: V3 kept failing on jq aggregation over NDJSON; one purpose-built aggregation tool fixed it.");

  // ---------- 7. Safety & integrity ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Safety and evaluation integrity");
  text(s, "Safety asymmetry", { x: M, y: 1.35, w: 6, h: 0.45, fontFace: HEAD, fontSize: 20, bold: true, color: STEEL });
  const lane = (y, a, b, c, fillC) => {
    box(M, y, 1.9, 0.9, a); arrow(s, 2.5, y + 0.45, 2.85, y + 0.45);
    box(2.85, y, 1.9, 0.9, b); arrow(s, 4.75, y + 0.45, 5.1, y + 0.45);
    box(5.1, y, 1.8, 0.9, c, fillC, WHITE);
  };
  lane(2.0, "Threat", "Write rule +\nreplay-validate", "Auto-deploy", "2E7D32");
  lane(3.2, "Benign noise", "Propose\nsuppression", "Human\napproval", RED);
  text(s, "A bad rule over-alerts (wrong-way safe). A bad suppression blinds the sensor (wrong-way unsafe) — so a human decides.", { x: M, y: 4.3, w: 6.3, h: 0.8, fontSize: 13, color: SLATE });
  card(s, M, 5.2, 6.3, 1.45, MIST);
  badge(s, "warn", M + 0.25, 5.45, 0.62, AMBER);
  text(s, "It mattered: one UNSW run proposed suppressing rules that were catching a real Cisco heap-overflow exploit. The proposal needed approval, so the sensor stayed sighted.",
    { x: M + 1.05, y: 5.3, w: 5.1, h: 1.25, fontSize: 13, valign: "middle" });
  text(s, "Evaluation integrity", { x: 7.35, y: 1.35, w: 5.4, h: 0.45, fontFace: HEAD, fontSize: 20, bold: true, color: STEEL });
  card(s, 7.35, 2.0, 5.38, 4.65, INK);
  badge(s, "lock", 7.6, 2.25, 0.62, AMBER);
  text(s, "Our transcript audit found label leakage", { x: 8.4, y: 2.3, w: 4.2, h: 0.55, fontSize: 15, bold: true, color: WHITE, valign: "middle" });
  s.addText([
    "Early runs listed the ground-truth folder — file names like '…PortScan' name the attack",
    "One Tuesday run read the answer from our own project notes",
    "Fix: tools can open only logs/, config/, rules/, data/pcaps/",
    "UNSW runs: zero attempts to read labels",
  ].map((t, i, a) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < a.length - 1 } })),
    { x: 7.6, y: 3.1, w: 4.9, h: 3.4, fontFace: BODY, fontSize: 14, color: WHITE, margin: 0, paraSpaceAfter: 8, valign: "top", isTextBox: true });
  s.addNotes("PRESENTER: Binay (≈1:00). Left: the asymmetry — the one design choice that protected us. Tell the Cisco exploit story briefly. Right: be upfront that we audited our own evaluation, found that some early runs could see answer-revealing file names and one run read our notes, and locked the tools down. This is why the Tuesday model comparison is reported as compromised. Hand over to Irab for data and results.");

  // ---------- 8. Datasets ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Two datasets, scored against ground truth");
  const ds = [
    ["CIC-IDS2017", "Canadian Institute for Cybersecurity", [["14", "attack categories"], ["4", "attack days, tuned + raw passes"], ["per-flow", "labels (CICFlowMeter)"]],
      "Brute force, DoS (Hulk, GoldenEye, slowloris, Slowhttptest), Heartbleed, web attacks, infiltration, DDoS, port scan, ARES botnet"],
    ["UNSW-NB15", "UNSW Canberra Cyber Range Lab", [["9", "attack categories"], ["6", "captures (12 GB), raw only"], ["31,432", "labelled attack events"]],
      "Never used during development — tests whether the approach transfers. No benign-only day, so no baseline tuning is possible"],
  ];
  ds.forEach(([name, org, st, desc], i) => {
    const x = M + i * 6.2;
    card(s, x, 1.4, 5.85, 5.25);
    badge(s, "db", x + 0.3, 1.65, 0.7, i ? AMBER : STEEL);
    text(s, name, { x: x + 1.2, y: 1.65, w: 4.4, h: 0.45, fontFace: HEAD, fontSize: 24, bold: true });
    text(s, org, { x: x + 1.2, y: 2.12, w: 4.4, h: 0.35, fontSize: 13, color: SLATE });
    st.forEach(([b, l], j) => {
      const sx = x + 0.3 + j * 1.85;
      text(s, b, { x: sx, y: 2.85, w: 1.8, h: 0.75, fontFace: HEAD, fontSize: b.length > 5 ? 26 : 36, bold: true, color: i ? AMBER : STEEL, valign: "bottom" });
      text(s, l, { x: sx, y: 3.65, w: 1.7, h: 0.7, fontSize: 12, color: SLATE });
    });
    text(s, desc, { x: x + 0.3, y: 4.65, w: 5.25, h: 1.8, fontSize: 14 });
  });
  s.addNotes("PRESENTER: Irab (≈0:40). CIC-IDS2017 is the development dataset: labelled flows for every attack. The supervisor asked us to try a second dataset in Week 9 — UNSW-NB15 — which the system had never seen. Every number that follows is measured against these labels, not taken from the model's own claims.");

  // ---------- 9. CIC results ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "CIC-IDS2017: broad coverage, precise rules");
  stat(s, "13 / 14", "attack categories identified by the model (only DoS GoldenEye missed)", M, 1.45, 4.3);
  stat(s, "8 → 12", "of 14 categories caught by rules: stock ET Open → stock + AI-authored rules", M, 3.1, 4.3, STEEL);
  stat(s, "99.4%", "of AI-rule alerts on the noisy days fell on real attack flows (stock rules: 6.1%)", M, 4.75, 4.3);
  s.addChart(pres.charts.BAR, [
    { name: "Stock ET Open", labels: ["Wed + Fri (noisy raw)", "All four days", "All days, excl. one bad rule"], values: [6.1, 81.2, 81.2] },
    { name: "AI-authored rules", labels: ["Wed + Fri (noisy raw)", "All four days", "All days, excl. one bad rule"], values: [99.4, 78.0, 99.6] },
  ], { x: 5.3, y: 1.4, w: 7.4, h: 5.1, barDir: "col", barGrouping: "clustered", chartColors: [GREY, STEEL],
       showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", valAxisMaxVal: 110, valAxisMinVal: 0, valAxisHidden: true,
       showLegend: true, legendPos: "t", legendFontFace: BODY, legendFontSize: 12, legendColor: INK,
       showTitle: true, title: "Precision: share of label-matched alerts on attack flows", titleFontFace: BODY, titleFontSize: 14, titleColor: INK, ...chartFrame });
  footer(s, "Flow-level matching on 5-tuple and time; Suricata engine events excluded. The one bad rule (FTP 'data staging') fires on routine uploads.");
  s.addNotes("PRESENTER: Irab (≈1:05). Three headline numbers. 13 of 14 attack types identified. Rules: stock ET caught 8 categories, adding the AI's rules takes it to 12. Precision: on the noisy captures almost every stock alert fell on normal traffic, almost every AI-rule alert on a real attack. Be honest about the middle bars — over all four days it is 81 vs 78 because of one bad AI rule; remove it and the AI rules are 99.6%.");

  // ---------- 10. Highlights ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "What the stock rules missed");
  const hl = [
    ["bug", "FAKEVERB DoS", "Diagnosed that Suricata's HTTP parser hides non-standard methods, rewrote the rule on raw TCP payload", "463 hits (stock: none)"],
    ["bolt", "Hulk GET flood", "149,703-request cache-busting flood with no dedicated stock rule; wrote and validated a rate rule", "new detection"],
    ["network", "ARES botnet", "Five infected hosts beaconing to a C2 server; no stock or custom alert had fired", "15 of 15 alerts on Bot flows"],
    ["search", "SSH brute force", "Paramiko client fingerprint rule for SSH-Patator", "detection 1.0% → 28.4%, zero false positives"],
  ];
  hl.forEach(([k, h, d, r], i) => {
    const x = M + (i % 2) * 6.2, y = 1.45 + Math.floor(i / 2) * 2.65;
    card(s, x, y, 5.85, 2.4);
    badge(s, k, x + 0.3, y + 0.3, 0.7, i === 2 ? AMBER : STEEL);
    text(s, h, { x: x + 1.2, y: y + 0.35, w: 4.4, h: 0.55, fontFace: HEAD, fontSize: 21, bold: true, valign: "middle" });
    text(s, d, { x: x + 0.3, y: y + 1.1, w: 5.25, h: 0.75, fontSize: 14 });
    text(s, r, { x: x + 0.3, y: y + 1.85, w: 5.25, h: 0.4, fontSize: 15, bold: true, color: AMBER });
  });
  s.addNotes("PRESENTER: Irab (≈1:00). Four short stories. FAKEVERB shows reasoning about the engine itself. Hulk: an attack class the 52,000-rule set had no dedicated rule for. ARES: listed as undetected in our interim report — found later by the model and confirmed by labels. SSH: a precise fingerprint rule that took detection from 1% to 28% with no false positives.");

  // ---------- 11. UNSW results ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "UNSW-NB15 v1: the approach works on a second dataset");
  const tot = unsw.gt_events_tcpudp, st_ = unsw.detected_tcpudp["stock"], ai_ = unsw.detected_tcpudp["stock+cic+unsw"];
  const cats = Object.keys(tot).sort((a, b) => (ai_[a] || 0) / tot[a] - (ai_[b] || 0) / tot[b]);
  const pct = (d, c) => +(100 * (d[c] || 0) / tot[c]).toFixed(1);
  s.addChart(pres.charts.BAR, [
    { name: "Stock ET Open", labels: cats, values: cats.map((c) => pct(st_, c)) },
    { name: "Stock + AI-authored rules", labels: cats, values: cats.map((c) => pct(ai_, c)) },
  ], { x: M, y: 1.35, w: 7.4, h: 5.3, barDir: "bar", barGrouping: "clustered", chartColors: [GREY, STEEL],
       showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", valAxisMaxVal: 45, valAxisMinVal: 0, valAxisHidden: true,
       showLegend: true, legendPos: "b", legendFontFace: BODY, legendFontSize: 12, legendColor: INK,
       showTitle: true, title: "TCP/UDP attack events detected, by category", titleFontFace: BODY, titleFontSize: 14, titleColor: INK, ...chartFrame });
  const sAll = (100 * Object.values(st_).reduce((a, b) => a + b, 0) / Object.values(tot).reduce((a, b) => a + b, 0)).toFixed(1);
  const aAll = (100 * Object.values(ai_).reduce((a, b) => a + b, 0) / Object.values(tot).reduce((a, b) => a + b, 0)).toFixed(1);
  stat(s, `${sAll}% → ${aAll}%`, "event-level detection, stock → stock + AI rules (+68% relative)", 8.3, 1.4, 4.45, AMBER, 36);
  stat(s, "8 / 9", "categories identified across six runs (Analysis missed)", 8.3, 2.95, 4.45, STEEL);
  stat(s, "0", "AI-rule alerts on hosts with no attacker involved", 8.3, 4.5, 4.45, STEEL);
  const v1 = J("unsw_v1_attribution.json");
  text(s, `Within one replay: +${(100 * v1.ai_new_genuine / v1.tcpudp).toFixed(1)} pts genuine gain over stock ET Open. 13 of 15 rules written on other captures fired on capture 14.`, { x: 8.3, y: 5.95, w: 4.45, h: 0.8, fontSize: 13, bold: true, color: INK });
  s.addNotes("PRESENTER: Irab (≈1:05). Same engine, unchanged, on a dataset it never saw. Detection rises from 9.2% to 15.5%; recon and exploits roughly double. IF ASKED WHY RECALL IS LOW: it is low for the professional stock rules too — UNSW fires thousands of one-off exploit attempts, many with no signature anywhere — so the claim is the improvement over human-written rules, achieved with zero alerts on benign hosts. Rules also transferred between captures. Hand over to Shashwat.");

  // ---------- 12. Experiment 1 ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Experiment 1: does context matter?", "Same model and captures (UNSW 3, 1, 10) — full sensor context versus alert events only");
  const f = exp1.full, b = exp1.bare;
  const ev = (c) => Object.values(c.findings.per_run).reduce((a, r) => a + r.outcome_statements - r.outcome_unconfirmed, 0);
  const mini = (x, ttl, vals, fmt, max) => s.addChart(pres.charts.BAR,
    [{ name: "Full context", labels: [" "], values: [vals[0]] }, { name: "Alerts only", labels: [" "], values: [vals[1]] }],
    { x, y: 1.8, w: 3.05, h: 3.2, barDir: "col", barGrouping: "clustered", chartColors: [STEEL, AMBER], showValue: true, dataLabelPosition: "outEnd",
      dataLabelFormatCode: fmt, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: max, showLegend: true, legendPos: "b", legendFontFace: BODY,
      legendFontSize: 11, legendColor: INK, showTitle: true, title: ttl, titleFontFace: BODY, titleFontSize: 13, titleColor: INK, ...chartFrame });
  mini(M, "GT events covered by findings", [+(100 * f.findings.covered_tcpudp / f.findings.tcpudp).toFixed(1), +(100 * b.findings.covered_tcpudp / b.findings.tcpudp).toFixed(1)], "0.0\"%\"", 36);
  mini(M + 3.15, "Detection with own rules", [+(100 * f.replay.cond_detected / f.replay.tcpudp_events).toFixed(1), +(100 * b.replay.cond_detected / b.replay.tcpudp_events).toFixed(1)], "0.0\"%\"", 16);
  mini(M + 6.3, "Evidence-backed outcome statements", [ev(f), ev(b)], "0", 65);
  card(s, 10.1, 1.8, 2.63, 3.2, INK);
  text(s, "Breadth without context.\nDepth with it.", { x: 10.3, y: 1.95, w: 2.25, h: 1.2, fontFace: HEAD, fontSize: 18, bold: true, color: AMBER });
  text(s, "Only full context let the model answer: did the attack succeed?", { x: 10.3, y: 3.2, w: 2.25, h: 1.6, fontSize: 14, color: WHITE });
  bullets(s, [
    "Alerts only covered more categories (7 vs 6) and wrote more productive rules — broad, signature-organised reports",
    "Full context established outcomes: '59 × PASS → 230 Login successful', '2.25 MB leaked by Heartbleed' — alerts-only reports said success 'cannot be confirmed'",
  ], { x: M, y: 5.3, w: W - 2 * M, h: 1.35, fontSize: 14 });
  s.addNotes("PRESENTER: Shashwat (≈1:15). This answers the second half of the research question, and the result surprised us. Without context the model was just as good — even slightly better — at spotting attacks. What context buys is depth: whether the attack actually worked, which decides the analyst's response. Caveats: one run per condition, and alert records still carry some flow counters.");

  // ---------- 13. What went wrong ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "What went wrong: confident errors");
  const errs = [
    ["trash", "Deleted two of its best rules, claiming they were stock ET rules — they were not"],
    ["bug", "Wrote three rules Suricata rejects and one that can never fire"],
    ["eye", "Read routine FTP uploads from every workstation as data exfiltration"],
    ["route", "'Validated' Thursday rules against a small test file, not the Thursday capture"],
    ["layers", "Same evidence, opposite verdicts across runs (5 : 1 on the Heartbleed rules)"],
  ];
  errs.forEach(([k, t], i) => {
    const y = 1.4 + i * 1.03;
    badge(s, k, M, y, 0.62, i === 0 ? RED : STEEL);
    text(s, t, { x: M + 0.85, y, w: 5.3, h: 0.62, fontSize: 14, valign: "middle" });
  });
  s.addChart(pres.charts.BAR, [
    { name: "Fired on replay", labels: ["CIC-IDS2017", "UNSW-NB15"], values: [16, 18] },
    { name: "Replayed, never fired", labels: ["CIC-IDS2017", "UNSW-NB15"], values: [4, 0] },
    { name: "Never replayed", labels: ["CIC-IDS2017", "UNSW-NB15"], values: [6, 0] },
    { name: "Cannot fire / fails to load", labels: ["CIC-IDS2017", "UNSW-NB15"], values: [4, 0] },
    { name: "Deleted by model", labels: ["CIC-IDS2017", "UNSW-NB15"], values: [2, 0] },
  ], { x: 7.0, y: 1.35, w: 5.7, h: 3.9, barDir: "bar", barGrouping: "stacked", chartColors: [STEEL, "7FA7C9", "CFD6DD", RED, "555555"],
       showValue: true, dataLabelPosition: "ctr", dataLabelFormatCode: "0;;;", dataLabelColor: WHITE, showLegend: true, legendPos: "b", legendFontFace: BODY, legendFontSize: 10, legendColor: INK,
       valAxisHidden: true, showTitle: true, title: "Audit of AI-authored rules, CIC + UNSW v1 (50)", titleFontFace: BODY, titleFontSize: 14, titleColor: INK, ...chartFrame, dataLabelColor: WHITE });
  card(s, 7.0, 5.45, 5.75, 1.2, INK);
  text(s, "Self-validation is only as good as the environment: CIC's config loaded 3 of 10 rule files; UNSW's loaded the model's file — and all 18 rules work.",
    { x: 7.2, y: 5.45, w: 5.35, h: 1.2, fontSize: 13, color: WHITE, valign: "middle" });
  s.addNotes("PRESENTER: Shashwat (≈1:00). Be candid — this is a strength of the evaluation, not a weakness of the talk. The errors are confident: the model reported success each time. The rule audit on the right covers all 50 AI-authored rules: 16 of the 32 CIC rules were proven by replay, all 18 UNSW rules. The pattern: on CIC many rules were never really tested because the configuration did not load their files; on UNSW, where it did, every rule works.");

  // ================= October additions: strong baseline, topology trap, engineer workflow, hold-out =================
  const FIGDIR = path.join(ROOT, "docs/figures");
  const fig = async (s, name, x, y, maxW, maxH) => {
    const p = path.join(FIGDIR, name);
    const m = await sharp(p).metadata();
    const r = Math.min(maxW / m.width, maxH / m.height);
    const w = m.width * r, h = m.height * r;
    s.addImage({ path: p, x: x + (maxW - w) / 2, y: y + (maxH - h) / 2, w, h });
  };
  const rounds = J("rounds.json"), ctrl = J("baseline_control.json"), gate = J("test_rule_gate.json");
  const pts = (n, d) => (100 * n / d);
  const section = (t, sub) => {
    const sl = pres.addSlide(); sl.background = { color: INK };
    sl.addText(t, { x: M, y: 2.6, w: W - 2 * M, h: 1.1, fontFace: HEAD, fontSize: 40, bold: true, color: WHITE, margin: 0, isTextBox: true });
    sl.addText(sub, { x: M, y: 3.75, w: W - 2 * M, h: 0.9, fontFace: BODY, fontSize: 20, color: AMBER, margin: 0, isTextBox: true });
    return sl;
  };

  // ---------- A. Section divider ----------
  s = section("Part 2 — Can the agent beat a strong human baseline?",
    "The supervisor's challenge: look at what real detection engineers do, and replicate it with the agent");
  s.addNotes("PRESENTER: Bigyan (≈0:20). Everything so far measured the AI against stock ET Open. In weeks 10-11 we asked the harder question: what happens when the human baseline is as strong as we can make it?");

  // ---------- B. Strengthening the baseline ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "First, make the human baseline as strong as possible", "Re-enabling disabled ET and Snort rule families, chosen from the services seen in the traffic — never from labels");
  await fig(s, "fig4-4_baseline_ladder.png", M, 1.6, 8.2, 5.1);
  const bD = pts(ctrl.baseline.det, ctrl.baseline.tcpudp), aD = pts(ctrl.allon.det, ctrl.allon.tcpudp);
  stat(s, "9.2% → 25.7%", "UNSW TCP/UDP attack events detected: ET Open as shipped → baseline v2", 9.1, 1.6, 3.7, STEEL, 32);
  stat(s, `${(ctrl.allon.no_attacker / ctrl.baseline.no_attacker).toFixed(0)}×`, `more alerts on non-attacker hosts if every disabled rule is enabled (${aD.toFixed(1)}% vs ${bD.toFixed(1)}% detection)`, 9.1, 3.3, 3.7, RED, 40);
  card(s, 9.1, 5.15, 3.65, 1.5, INK);
  text(s, "This is the bar the AI now has to clear — no longer stock rules.", { x: 9.3, y: 5.15, w: 3.3, h: 1.5, fontSize: 14, color: WHITE, valign: "middle" });
  footer(s, "Six development captures (17 Feb 2015), 14,935 TCP/UDP attack events. Extra rulesets: Snort Community, Stamus lateral, PT Open, Nmap (Nmap later dropped: it wrecked CIC precision).");
  s.addNotes("PRESENTER: Irab (≈0:50). A real SOC engineer's first move is not AI, it is tuning the rules they have. Adding more rulesets did almost nothing; re-enabling the rule families that ship disabled, picked by which services are under attack, nearly tripled detection. Enabling everything gets 31% but floods non-attacker hosts with 46x the alerts — that is why we chose by service.");

  // ---------- C. Where the misses are ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Where a signature IDS still misses", "Baseline v2 detection by attack category — most attack events are still missed in every category");
  await fig(s, "fig4-6_category_ceiling.png", M, 1.55, 8.0, 5.2);
  const bc = ctrl.baseline, cp = (c) => (100 * (bc.detected_by_cat[c] || 0) / bc.tcpudp_by_cat[c]).toFixed(0) + "%";
  bullets(s, [
    `Roughly a quarter to a third caught in the big categories: Exploits ${cp("Exploits")}, Fuzzers ${cp("Fuzzers")}, Reconnaissance ${cp("Reconnaissance")}`,
    `Weakest: Generic ${cp("Generic")} of ${bc.tcpudp_by_cat["Generic"].toLocaleString()} events, Analysis ${cp("Analysis")}, DoS ${cp("DoS")}`,
    "Most missed events are one-off attempts generated with varying content — a rule written for one instance rarely matches the next",
  ], { x: 8.9, y: 1.7, w: 3.85, h: 4.9, fontSize: 14 });
  s.addNotes("PRESENTER: Irab (≈0:40). This chart explains every result that follows. Even the best categories are only a quarter to a third detected, and Generic — almost 2,700 events — is at 7%. The traffic generator varies each attempt, so a rule for one instance rarely matches the next. Keep this in mind when we look at what the AI added.");

  // ---------- D. The topology trap ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "AI rounds on the strong baseline: the topology trap", "Rule-writing rounds on captures 3, 1, 10; scored on all six. Gains attributed only to events no other alert caught.");
  await fig(s, "fig5-7_rounds_attribution.png", M, 1.55, 7.6, 4.15);
  await fig(s, "fig5-8_rule_classes.png", 8.3, 1.65, 4.45, 2.6);
  card(s, 8.3, 4.45, 4.45, 2.3, MIST);
  text(s, "Topology rule = ordinary activity from outside HOME_NET (SMTP MAIL FROM, POP3 login, SIP REGISTER). In UNSW every external host is an attacker, so these score perfectly here — and would alert on every customer on a real network.",
    { x: 8.5, y: 4.55, w: 4.1, h: 2.1, fontSize: 12.5 });
  const pr2 = rounds["plain-r2"], rr2 = rounds["research-r2"];
  card(s, M, 5.85, 7.6, 0.85, INK);
  const hr1 = rounds["hunt-r1"];
  text(s, `Plain R2 looked like +${pts(pr2.ai_new, pr2.tcpudp).toFixed(1)} pts, genuine +${pts(pr2.ai_new_genuine, pr2.tcpudp).toFixed(2)}. Research: +${pts(rr2.ai_new_genuine, rr2.tcpudp).toFixed(2)}. Hunt / hunt2: +${pts(hr1.ai_new_genuine, hr1.tcpudp).toFixed(2)} / +${pts(rounds["hunt2-r1"].ai_new_genuine, rounds["hunt2-r1"].tcpudp).toFixed(2)} — the only gains clearly above noise.`,
    { x: M + 0.2, y: 5.85, w: 7.2, h: 0.85, fontSize: 13.5, color: WHITE, valign: "middle", bold: true });
  s.addNotes("PRESENTER: Shashwat (≈1:00). We caught ourselves here. The plain condition seemed to add 11 points. Classifying every rule by its text showed most of it was topology — 'an outsider sent mail' — which is only an attack because of how UNSW is built. We also found our scoring compared a fresh replay with an old one; Suricata's thresholds are not deterministic, so we now credit only events that the AI rules alone caught. Honest numbers: plain and research add well under half a point; only the two hunt conditions clearly add detection — next slides.");

  // ---------- E. Engineer workflow ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Replicating a real detection engineer", "Hunt condition: the detection-engineering lifecycle, encoded as the agent's procedure");
  await fig(s, "fig3-6_hunt_workflow.png", M, 1.55, 8.4, 4.4);
  const src = [["Palantir ADS", "every rule documents goal, blind spots, false positives"],
               ["SpecterOps", "detect the technique, not the tool's surface strings"],
               ["Stack counting", "rare values first — no ML, no training period"],
               ["RuleAutoPilot (2026)", "execution-grounded validation: F1 0.443 → 0.539"]];
  src.forEach(([h, d], i) => {
    const y = 1.6 + i * 1.12;
    card(s, 9.25, y, 3.5, 0.98);
    text(s, h, { x: 9.4, y: y + 0.08, w: 3.2, h: 0.35, fontSize: 13.5, bold: true, color: STEEL });
    text(s, d, { x: 9.4, y: y + 0.45, w: 3.2, h: 0.5, fontSize: 11.5, color: SLATE });
  });
  card(s, M, 6.05, W - 2 * M, 0.7, INK);
  text(s, "No attacker range in the prompt. Two new tools: stack_values (rare-first counting) and test_rule. The engine refuses to save any rule that has not passed test_rule in exactly that form.",
    { x: M + 0.2, y: 6.05, w: W - 2 * M - 0.4, h: 0.7, fontSize: 13, color: WHITE, valign: "middle" });
  s.addNotes("PRESENTER: Binay (≈1:00). This is the supervisor's suggestion made concrete. We researched how detection engineers work — Palantir's ADS framework, SpecterOps, threat-hunting practice — and turned it into the agent's procedure. The key differences from the earlier rounds: it starts from traffic nothing alerted on instead of from alerts, it never sees the attacker range, and it cannot save a rule without passing a test.");

  // ---------- F. The gate ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "The anti-topology gate", "Replay the rule as written, then widened to any → any. If it fires between internal hosts, it is matching normal activity.");
  await fig(s, "fig3-7_test_rule_gate.png", M, 1.55, 7.3, 3.75);
  await fig(s, "fig5-9_gate_coverage.png", 8.05, 1.6, 4.7, 3.3);
  bullets(s, [
    `Known-good = internal clients → servers (testbed documentation: servers 1 and 3 generate normal traffic)`,
    `${gate.replay_seconds} s per test on a 2 GB capture — cheap enough for the agent to iterate`,
    "Limitation: blind on POP3, SIP and SMB — no internal host uses them in UNSW",
  ], { x: M, y: 5.5, w: W - 2 * M, h: 1.3, fontSize: 14 });
  s.addNotes("PRESENTER: Binay (≈0:50). The test is simple and checkable. The MAIL FROM rule looks perfect when written from outside — 173 hits. Remove the address constraint and it matches 1,668 normal internal emails: the rule's precision came from the IP address, not the behaviour. A directory-traversal rule passes: same hits either way. Be upfront about where the test is blind.");

  // ---------- G0. The bug ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "We found a bug by watching the agent fail", "Capture 1, first attempt: 100 turns, 8.4M tokens, rules passed the gate — and nothing was saved");
  const bug = [
    ["warn", "Symptom", "Re-tested rules that had already passed, never saved, hit the 100-turn limit. The UI showed tool calls but no reasoning at all."],
    ["search", "Diagnosis", "Engine, server and browser all passed text through. The raw API did not: DeepSeek V4 Pro answered in thinking mode — reasoning in reasoning_content, content empty."],
    ["bug", "Root cause", "Our adapter read only content. The model's reasoning was never logged and never sent back, so every turn it started again without its own plan."],
    ["check", "Fix", "Stream reasoning to the UI and transcript, and return it with each turn. Re-run: finished in 90 turns, 9 rules saved, 5.2M tokens."],
  ];
  bug.forEach(([k, h, d], i) => {
    const y = 1.6 + i * 1.22;
    card(s, M, y, W - 2 * M, 1.08);
    badge(s, k, M + 0.25, y + 0.22, 0.62, i === 3 ? "2E7D32" : i === 2 ? RED : STEEL);
    text(s, h, { x: M + 1.1, y: y + 0.1, w: 2.2, h: 0.85, fontFace: HEAD, fontSize: 18, bold: true, valign: "middle" });
    text(s, d, { x: M + 3.2, y: y + 0.1, w: W - 2 * M - 3.5, h: 0.88, fontSize: 14, valign: "middle" });
  });
  footer(s, "Every earlier DeepSeek run carried the same defect whenever the model used thinking mode; most also wrote visible text, so they were affected less. Stated as a threat to validity.");
  s.addNotes("PRESENTER: Binay (≈1:00). This is the real-engineering story. The supervisor asked us to replicate what detection engineers do; when the agent behaved oddly we debugged it like engineers — checked each layer until the raw API showed the reasoning was arriving in a field we ignored. One fix, and the next run finished on its own.");

  // ---------- G. Hunt results ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  const hr = rounds["hunt-r1"];
  title(s, "Hunt result: technique rules that transfer", "25 rules from captures 3, 1, 10 — capture 3 ran before the fix, captures 1 and 10 after it");
  await fig(s, "fig5-10_hunt_transfer.png", M, 1.5, 7.9, 5.3);
  stat(s, `+${pts(hr.ai_new_genuine, hr.tcpudp).toFixed(2)} pts`, `genuine detection on the 6 dev captures (+${hr.ai_new_genuine} events no other rule caught)`, 8.75, 1.45, 4.0, STEEL, 34);
  stat(s, `${(100 * hr.ai_gt / hr.ai_alerts).toFixed(0)}%`, "of hunt-rule alerts match a labelled attack; 0 on normal hosts; 0 topology rules", 8.75, 3.0, 4.0, AMBER, 38);
  stat(s, "6 → 175", "events added by rules written before the fix (instances) vs after it (techniques)", 8.75, 4.55, 4.0, "2E7D32", 34);
  footer(s, "Top contributors: SMB fuzzed filenames (behavioural, +59), HTTP /../ traversal (+37), HP HPEinc file inclusion (+31), encoded XSS (+24). The SMB rule could not be gate-tested (no internal SMB); 0 alerts on benign hold-out captures.");
  s.addNotes("PRESENTER: Shashwat (≈1:00). Read the chart by group. Capture 3's rules (before the fix) each match one exploit attempt and never fire again. Captures 1 and 10, after the fix, wrote technique and behaviour rules — traversal, XSS, format strings, SMB fuzzing — and most fire on captures they were never written on. Be honest: the improvement coincides with the bug fix, so we cannot separate 'better workflow' from 'reasoning carried'. Both were needed.");

  // ---------- H. Hold-out ----------
  if (rounds["hunt-r1-holdout"]) {
    const ho = rounds["baseline-holdout"], hh = rounds["hunt-r1-holdout"], ex = rounds.holdout_extra;
    s = pres.addSlide(); s.background = { color: WHITE };
    title(s, "Hold-out: traffic nobody had looked at", "UNSW 22 Jan 2015 — rule files frozen first, then replayed and scored once");
    await fig(s, "fig5-12_generalisation.png", M, 1.5, 7.9, 4.3);
    stat(s, `+${pts(hh.ai_new_genuine, hh.tcpudp).toFixed(2)} pts`, `hunt rules on the hold-out (+${hh.ai_new_genuine} of ${hh.tcpudp.toLocaleString()} events) — larger than on the dev set`, 8.75, 1.45, 4.0, STEEL, 34);
    stat(s, "0", "AI-rule alerts on the two benign-only hold-out captures, in every condition", 8.75, 3.0, 4.0, "2E7D32", 44);
    stat(s, `${pts(ho.base_det, ho.tcpudp).toFixed(1)}%`, "detected by the frozen human baseline v2 alone (dev: 24.9%)", 8.75, 4.55, 4.0, AMBER, 34);
    footer(s, `Hunt2: +${pts(rounds["hunt2-r1-holdout"].ai_new_genuine, rounds["hunt2-r1-holdout"].tcpudp).toFixed(2)} pts. All four conditions together: about +${ex.combined.pts.toFixed(1)} pts. Plain and research: +0.11 and +0.28 — their large raw gains were topology rules.`);
    s.addNotes("PRESENTER: Irab (≈0:50). This is the number that matters most. We froze every rule file, then ran the untouched day once. The hunt rules' gain held — slightly larger than on the development captures — and no AI rule fired on the two captures with only normal traffic. The human baseline also generalised. Caveat: still small against the ~70% of events every ruleset misses.");
  }

  // ---------- I. Hunt2 ----------
  {
    const h2 = rounds["hunt2-r1"], h2h = rounds["hunt2-r1-holdout"], un = J("rounds_unseen_dev.json");
    s = pres.addSlide(); s.background = { color: WHITE };
    title(s, "Hunt2: the keyword tool fixed errors, not detection", "Same workflow plus suricata_keywords (which rule keywords this Suricata supports); all runs after the fix");
    await fig(s, "fig5-14_hunt_overlap.png", M, 1.55, 8.0, 3.6);
    stat(s, "0", "rules that failed to load (hunt capture 10: 2); proper buffers instead of raw-byte regexes", 8.85, 1.45, 3.9, "2E7D32", 40);
    stat(s, `+${pts(h2.ai_new_genuine, h2.tcpudp).toFixed(2)} / +${un["hunt2-r1"].pts.toFixed(2)} / +${pts(h2h.ai_new_genuine, h2h.tcpudp).toFixed(2)}`,
         "genuine pts: dev / dev 4-5-14 / hold-out (hunt: +1.21 / +1.38 / +1.53)", 8.85, 3.0, 3.9, STEEL, 28);
    stat(s, "82 shared", "of 180 (hunt) and 136 (hunt2) events: runs of the same workflow find different attacks", 8.85, 4.55, 3.9, AMBER, 30);
    footer(s, "Expected beforehand: +1.2 to +2.0 pts. Got less. What a run detects depends on which attack families it chooses to hunt — run-to-run variation is larger than the tool's effect.");
    s.addNotes("PRESENTER: Bigyan (≈0:50). We predicted the keyword tool would help. It did fix what it targeted — no rule failed to load — but detection went slightly down, because this run hunted different attack families. The two runs share only 82 events. So the bottleneck is not knowing Suricata's syntax; it is which attacks the agent decides to chase. Running several times and keeping the union is the obvious next step.");
  }

  // ---------- J. Detectability ----------
  {
    const dt = J("detectable.json");
    s = pres.addSlide(); s.background = { color: WHITE };
    title(s, "Is 25% unfair to a signature IDS?", "Measured against attacks a rule could plausibly see — not every labelled event");
    await fig(s, "fig5-13_detectability.png", M, 1.5, 8.4, 4.0);
    stat(s, `${(100 * dt.dev.content / dt.dev.tcpudp).toFixed(0)}%`, "of attack events carried data a content rule could see", 9.25, 1.45, 3.5, STEEL, 40);
    stat(s, `${(100 * dt.dev.base.content / dt.dev.content).toFixed(1)}%`, "of those the tuned baseline detects — the gap is unwritten signatures", 9.25, 3.0, 3.5, RED, 40);
    stat(s, `+${(100 * dt.holdout.gains.hunt.all / dt.holdout.ever).toFixed(1)} pts`, "hunt gain measured against everything any configuration caught (hold-out)", 9.25, 4.55, 3.5, AMBER, 34);
    footer(s, "Content-detectable: attacker sent more bytes than headers account for (PSH flag unusable: the generator omits it). Ever-detected: caught by any configuration we ran — a circular ceiling.");
    s.addNotes("PRESENTER: Irab (≈0:45). A fair question: maybe most attacks are undetectable by signatures. They are not — three-quarters carried data, and the baseline still misses three-quarters of those. Against what anything we ran could catch, the human baseline is already at 74-93%, and the hunt adds about 4-5 points of that ceiling.");
  }

  // ---------- K. Agent limits ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Why the agent did not write a rule", "Attack-like activity the hunt reports left without a rule, grouped by cause");
  await fig(s, "fig5-15_agent_limits.png", M, 1.5, W - 2 * M, 5.1);
  s.addNotes("PRESENTER: Shashwat (≈0:40). Four causes. The tooling gap we fixed with hunt2. The rule-language limit — DNS entropy needs Lua. Our own design: no IP pivots and a gate that cannot test POP3 or SIP mean rate rules were off the table, by choice. And some omissions were simply right.");

  // ---------- 14. Conclusions ----------
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Conclusions");
  card(s, M, 1.35, W - 2 * M, 1.5, INK);
  s.addText([{ text: "Answer — a split claim: ", options: { bold: true, color: AMBER } },
             { text: "yes for triage: with sensor context the model investigates end to end (13/14 CIC, 8/9 UNSW categories) and establishes outcomes. Partly for detection: against a strong human-tuned baseline, triage-driven rules added a fraction of a point; the detection-engineering workflow, with the model's reasoning carried across turns, added +1.2–1.5 pts (hunt2: ~+1.0) that held on unseen traffic with no false alarms — real, but modest against the ~70% still missed.", options: { color: WHITE } }],
    { x: M + 0.4, y: 1.35, w: W - 2 * M - 0.8, h: 1.5, fontFace: BODY, fontSize: 16.5, valign: "middle", margin: 0, isTextBox: true });
  const lessons = [
    ["cogs", "Tools and procedure shape the agent", "count_by fixed a failing model; the hunt procedure removed topology rules"],
    ["shield", "Carry the model's reasoning", "Dropping it made the agent loop; returning it fixed the hunt"],
    ["check", "Measure what the AI alone caught", "Replay variance and topology rules both inflated our early numbers"],
    ["search", "Techniques transfer, instances don't", "Per-exploit rules fired once; traversal, XSS and fuzzing rules held on the hold-out"],
  ];
  lessons.forEach(([k, h, d], i) => {
    const x = M + (i % 2) * 6.2, y = 3.2 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 5.85, 1.5);
    badge(s, k, x + 0.3, y + 0.42, 0.66, i === 1 ? AMBER : STEEL);
    text(s, h, { x: x + 1.2, y: y + 0.2, w: 4.45, h: 0.5, fontFace: HEAD, fontSize: 16, bold: true, valign: "middle" });
    text(s, d, { x: x + 1.2, y: y + 0.75, w: 4.45, h: 0.6, fontSize: 14, color: SLATE });
  });
  s.addNotes("PRESENTER: Shashwat (≈1:00). Give the split answer, then the four lessons. Mention that model-agnosticism is a design property here, not a proven result — the Tuesday comparison was compromised by the label leakage we found.");

  // ---------- 15. Future work & Q&A ----------
  s = pres.addSlide(); s.background = { color: INK };
  s.addText("Next steps", { x: M, y: 0.6, w: 7, h: 0.8, fontFace: HEAD, fontSize: 36, bold: true, color: WHITE, margin: 0, isTextBox: true });
  const nxt = [["check", "Separate workflow from fix", "Re-run plain and research with reasoning carried, to isolate what the hunt workflow adds"],
               ["search", "Technique-level hunting", "Require technique rules and test each on a second capture before saving"],
               ["users", "Several runs per capture", "Runs find different attacks: keep the union, measure the spread"],
               ["network", "Live deployment", "Time-windowed alert batches and live rule reload via the Suricata socket"]];
  nxt.forEach(([k, h, d], i) => {
    const y = 1.7 + i * 1.2;
    badge(s, k, M, y, 0.66, AMBER);
    text(s, h, { x: M + 0.95, y: y - 0.02, w: 6.4, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true, color: WHITE });
    text(s, d, { x: M + 0.95, y: y + 0.38, w: 6.4, h: 0.7, fontSize: 14, color: "CADCFC" });
  });
  s.addImage({ data: IC.shieldAmber, x: 9.6, y: 1.6, w: 2.4, h: 2.4 });
  s.addText("Questions?", { x: 8.3, y: 4.4, w: 4.6, h: 0.9, fontFace: HEAD, fontSize: 40, bold: true, color: AMBER, align: "center", margin: 0, isTextBox: true });
  s.addText("Code, rules, transcripts and evaluation scripts:\ngithub.com/bigyan-siwakoti/Intrusion_Detection_System", { x: 8.0, y: 5.4, w: 5.0, h: 0.8, fontFace: BODY, fontSize: 13, color: "CADCFC", align: "center", margin: 0, isTextBox: true });
  s.addNotes("PRESENTER: Shashwat (≈0:30), then all four for questions. Likely questions: (1) Why is recall low? — low for the human-written stock rules too; we measure improvement. (2) Why DeepSeek for most runs? — cost; the adapter makes the model swappable. (3) Could the model have seen the answers? — we found and fixed that; UNSW runs had zero label access.");

  await pres.writeFile({ fileName: OUT });
  console.log("Saved", OUT);
})();
