"""Build the final-report draft from the team's 'report draft.docx'.

Every added or corrected word is red; superseded text is removed (team decision, 4 Oct 2026), so the red
text is exactly what changed since the team's draft.
Figures come from docs/figures/ (src/eval/make_figures.py); numbers from docs/results/.
Re-run after Experiment 1 results are available.

Usage: venv/bin/python docs/build_final_report.py
"""

import copy
import csv
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

DOCS = Path(__file__).resolve().parent
SRC = DOCS / "report draft.docx"
DST = DOCS / "Final_Report_Group13_DRAFT.docx"
FIG = DOCS / "figures"
RED = RGBColor(0xFF, 0x00, 0x00)

d = Document(SRC)
BODY = d.element.body


# ---------------------------------------------------------------- locating

def para(prefix: str) -> Paragraph:
    hits = [p for p in d.paragraphs if p.text.strip().startswith(prefix) and not p.style.name.lower().startswith("toc")]
    assert len(hits) == 1, f"{len(hits)} paragraphs start with {prefix!r}"
    return hits[0]


def table(first_cell: str) -> Table:
    hits = [t for t in d.tables if t.rows[0].cells[0].text.strip().startswith(first_cell)]
    assert len(hits) == 1, f"{len(hits)} tables start with {first_cell!r}"
    return hits[0]


def row(t: Table, first_cell: str):
    hits = [r for r in t.rows if r.cells[0].text.strip().startswith(first_cell)]
    assert len(hits) == 1, f"{len(hits)} rows start with {first_cell!r}"
    return hits[0]


# ---------------------------------------------------------------- run surgery

def _split(run: Run, offset: int) -> Run:
    """Split run at offset; returns the new right-hand run."""
    text = run.text
    new = copy.deepcopy(run._r)
    run._r.addnext(new)
    right = Run(new, run._parent)
    run.text, right.text = text[:offset], text[offset:]
    return right


def _isolate(p: Paragraph, start: int, end: int) -> list:
    pos, out = 0, []
    for r in list(p.runs):
        n = len(r.text)
        rs, re_ = pos, pos + n
        pos = re_
        if re_ <= start or rs >= end or n == 0:
            continue
        cur = r
        if start > rs:
            cur = _split(cur, start - rs)
            rs = start
        if end < re_:
            _split(cur, end - rs)
        out.append(cur)
    return out


def _red_run_after(anchor_r, text: str, bold=None) -> Run:
    new = copy.deepcopy(anchor_r)
    anchor_r.addnext(new)
    r = Run(new, None)
    r.text = text
    r.font.strike = False
    r.font.color.rgb = RED
    if bold is not None:
        r.bold = bold
    return r


def rtext(p: Paragraph) -> str:
    return "".join(r.text for r in p.runs)


def strike(p: Paragraph, old: str, new: str = None):
    """Remove `old` (must be unique in p) and put `new` in red in its place. A paragraph left empty is removed."""
    full = rtext(p)
    assert full.count(old) == 1, f"{full.count(old)} x {old!r} in {full[:60]!r}"
    s = full.index(old)
    runs = _isolate(p, s, s + len(old))
    if new:
        lead = s > 0 and not full[s - 1].isspace() and not new.startswith((" ", ",", ".", ";"))
        _red_run_after(runs[-1]._r, (" " if lead else "") + new)
    for r in runs:
        r._r.getparent().remove(r._r)
    if not rtext(p).strip() and not p._p.xpath(".//w:drawing"):
        p._p.getparent().remove(p._p)


def replace_plain(p: Paragraph, old: str, new: str):
    """For headings/captions: Word's generated lists copy struck text, so replace outright (red)."""
    full = rtext(p)
    assert full.count(old) == 1, f"{full.count(old)} x {old!r}"
    s = full.index(old)
    runs = _isolate(p, s, s + len(old))
    runs[0].text = new
    runs[0].font.color.rgb = RED
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def strike_all(p: Paragraph, new: str):
    strike(p, rtext(p), new)


def insert_after_text(p: Paragraph, anchor: str, text: str):
    full = rtext(p)
    assert full.count(anchor) == 1, f"{full.count(anchor)} x {anchor!r}"
    e = full.index(anchor) + len(anchor)
    runs = _isolate(p, 0, e)
    _red_run_after(runs[-1]._r, text, bold=False)


def append(p: Paragraph, text: str):
    runs = [r for r in p.runs if r.text]
    if runs:
        _red_run_after(runs[-1]._r, text, bold=False).italic = runs[-1].italic
    else:
        r = p.add_run(text)
        r.font.color.rgb = RED


# ---------------------------------------------------------------- new blocks

T_BODY = para("IDP systems (IDS) are a fundamental")._p
T_H1 = para("List of Abbreviations")._p
T_H2 = para("Model Comparison")._p
T_CAPTION = para("Table 4-1: CIC-IDS2017 dataset structure")._p
T_REF = para("Denning, DE 1987")._p


def _clone_para(template, anchor, where="after") -> Paragraph:
    new = copy.deepcopy(template)
    for child in list(new):
        if child.tag != qn("w:pPr"):
            new.remove(child)
    (anchor.addnext if where == "after" else anchor.addprevious)(new)
    return Paragraph(new, d._body)


def new_para(anchor, segments, template=T_BODY, where="after", size=None, italic=None) -> Paragraph:
    """segments: str or list of (text, bold)."""
    p = _clone_para(template, anchor, where)
    if isinstance(segments, str):
        segments = [(segments, False)]
    for text, bold in segments:
        r = p.add_run(text)
        r.bold = bold or None
        r.font.color.rgb = RED
        if size:
            r.font.size = Pt(size)
        if italic:
            r.italic = True
    return p


class Cursor:
    """Sequential inserter: each new block goes after the previous one."""

    def __init__(self, anchor):
        self.el = anchor._p if isinstance(anchor, Paragraph) else anchor

    def _push(self, obj):
        self.el = obj._p if isinstance(obj, Paragraph) else obj._tbl if isinstance(obj, Table) else obj
        return obj

    def p(self, segments, **kw):
        return self._push(new_para(self.el, segments, **kw))

    def h1(self, text):
        return self._push(new_para(self.el, text, template=T_H1))

    def h2(self, text):
        return self._push(new_para(self.el, text, template=T_H2))

    def caption(self, text, kind):
        p = new_para(self.el, text, template=T_CAPTION, italic=True, size=10)
        for r in p.runs:
            r.font.name = "Times New Roman"
        p.style = d.styles[f"{kind} Caption"]
        return self._push(p)

    def figure(self, png, caption, width=6.0):
        d.add_picture(str(FIG / png), width=Inches(width))
        pic = d.paragraphs[-1]
        pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.el.addnext(pic._p)
        self._push(pic)
        return self.caption(caption, "Figure")

    def table(self, template: Table, rows, ncols, font=None, widths=None):
        t = clone_table(template, rows, ncols, font, widths)
        self.el.addnext(t._tbl)
        return self._push(t)


def set_cell(cell, text, font=None, bold=None):
    ps = cell.paragraphs
    for extra in ps[1:]:
        extra._p.getparent().remove(extra._p)
    p = ps[0]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    r = p.add_run(text)
    r.font.color.rgb = RED
    if font:
        r.font.size = Pt(font)
    if bold is not None:
        r.bold = bold


def cell_strike(cell, old, new=None):
    strike(cell.paragraphs[0], old, new)


def cell_append(cell, text):
    append(cell.paragraphs[-1], text)


def clone_table(template: Table, rows, ncols, font=None, widths=None) -> Table:
    tbl = copy.deepcopy(template._tbl)
    t = Table(tbl, d._body)
    grid = tbl.find(qn("w:tblGrid"))
    gcols = grid.findall(qn("w:gridCol"))
    total = sum(int(g.get(qn("w:w"))) for g in gcols)
    for g in gcols[ncols:]:
        grid.remove(g)
    for tr in tbl.findall(qn("w:tr")):
        for tc in tr.findall(qn("w:tc"))[ncols:]:
            tr.remove(tc)
    widths = widths or [1] * ncols
    for g, w in zip(grid.findall(qn("w:gridCol")), widths):
        g.set(qn("w:w"), str(int(total * w / sum(widths))))
    for tr in tbl.findall(qn("w:tr")):
        for tc, w in zip(tr.findall(qn("w:tc")), widths):
            tcw = tc.find(qn("w:tcPr") + "/" + qn("w:tcW"))
            if tcw is not None:
                tcw.set(qn("w:w"), str(int(total * w / sum(widths))))
                tcw.set(qn("w:type"), "dxa")
    trs = tbl.findall(qn("w:tr"))
    header, body_tpl = trs[0], trs[1]
    for tr in trs[1:]:
        tbl.remove(tr)
    for _ in rows[1:]:
        tbl.append(copy.deepcopy(body_tpl))
    t = Table(tbl, d._body)
    for r_i, values in enumerate(rows):
        for c_i, v in enumerate(values):
            set_cell(t.rows[r_i].cells[c_i], str(v), font, bold=True if r_i == 0 else None)
    return t


def add_row(t: Table, values, font=None):
    new = copy.deepcopy(t.rows[-1]._tr)
    t._tbl.append(new)
    for cell, v in zip(t.rows[-1].cells, values):
        set_cell(cell, v, font)


# ---------------------------------------------------------------- styles & fields

def create_caption_styles():
    for kind in ("Figure", "Table"):
        name = f"{kind} Caption"
        if name not in [s.name for s in d.styles]:
            st = d.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            st.base_style = d.styles["Normal"]
            st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER


def caption_styles():
    for p in d.paragraphs:
        t = p.text.strip()
        if t.startswith("Fig. ") and p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            p.style = d.styles["Figure Caption"]
        elif t.startswith("Table ") and p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            p.style = d.styles["Table Caption"]


def _fld(p: Paragraph, kind: str, instr: str = None):
    r = OxmlElement("w:r")
    if kind == "instr":
        it = OxmlElement("w:instrText")
        it.set(qn("xml:space"), "preserve")
        it.text = instr
        r.append(it)
    else:
        fc = OxmlElement("w:fldChar")
        fc.set(qn("w:fldCharType"), kind)
        r.append(fc)
    p._p.append(r)


def list_field(cur: Cursor, title: str, style: str, entries):
    cur.h1(title)
    first = cur.p([])
    _fld(first, "begin"); _fld(first, "instr", f' TOC \\h \\z \\t "{style},1" '); _fld(first, "separate")
    r = first.add_run(entries[0]); r.font.color.rgb = RED
    last = first
    for e in entries[1:]:
        last = cur.p(e)
    _fld(last, "end")


def update_fields_on_open():
    settings = d.settings.element
    el = settings.find(qn("w:updateFields"))
    if el is None:
        el = OxmlElement("w:updateFields")
        # Schema order: updateFields precedes these siblings in CT_Settings.
        later = ["hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
                 "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
                 "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown", "smartTagType",
                 "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol", "listSeparator"]
        nxt = next((c for c in settings if c.tag.split("}")[1] in later), None)
        (nxt.addprevious(el) if nxt is not None else settings.append(el))
    el.set(qn("w:val"), "true")


# ================================================================ EDITS
create_caption_styles()

# ---- Front matter
strike(para("Due date:"), "September 2026", "October 2026")
p = para("I hereby declare that the work herein")
strike(p, "submitted as an interim report", "submitted as a final report")
strike(p, "embodied in this interim report", "embodied in this report")
strike(para("Date:  06 September 2026"), "06 September 2026", "[submission date] October 2026")

abbr = table("Abbreviation")
add_row(abbr, ["GT", "Ground Truth"], 9)
add_row(abbr, ["UNSW", "University of New South Wales"], 9)

# ---- Glossary of project terms (after the abbreviations table)
GLOSSARY = [
    ["Term", "Meaning in this report"],
    ["Ground truth (GT)", "The dataset's own labels of which traffic is an attack (CIC-IDS2017 labelled flows; UNSW-NB15 NUSW-NB15_GT.csv events). Used only for scoring; the model never sees it."],
    ["Development (dev) set", "The six UNSW-NB15 captures from 17 February 2015 (1, 3, 4, 5, 10, 14) on which rule families were chosen and AI rules were written and scored."],
    ["Hold-out", "UNSW-NB15 captures from 22 January 2015 (1, 3, 6 for detection; 25, 50 benign-only) kept untouched until every rule file was frozen, then scored once."],
    ["Baseline v2", "The strengthened human-written rule set: ET Open plus Snort Community, Stamus lateral, PT Open and the ET/Snort rule families that ship disabled, selected by the services seen in the traffic. Frozen; contains no AI rules."],
    ["All-rules control", "Baseline v2 with every disabled rule enabled; used to show the cost in noise of not selecting families."],
    ["Experiment profile", "A named, frozen bundle that fixes a run's dataset, Suricata configuration, writable rule file, tools, prompt and blocked files (src/profiles.py)."],
    ["Plain condition", "Profile unsw-v2-plain: alert triage on baseline v2 with the search_rules tool."],
    ["Research condition", "Profile unsw-v2-research: plain plus lookup_vulnerability, a local copy of the NVD database."],
    ["Hunt condition", "Profile unsw-v2-hunt: the detection-engineering workflow (coverage map, rare-value hunting, hypothesis, rule with ADS comment, test_rule, save), without the attacker range in the prompt."],
    ["Hunt2 condition", "Profile unsw-v2-hunt2: the hunt condition plus the suricata_keywords tool; otherwise identical."],
    ["Round (R1, R2)", "One pass of rule writing over captures 3, 1 and 10 in turn, followed by scoring on all six development captures; a second round starts from the first round's rules."],
    ["stack_values", "Tool that counts the values of any eve.json field and lists the rarest first (stack counting / long-tail analysis)."],
    ["test_rule (the gate)", "Tool that checks a rule's syntax, replays a capture with only that rule, then replays it with its addresses widened to any → any. FAIL if it raises no alerts or if the widened rule fires between internal hosts. The engine refuses to save a rule that has not passed in exactly that form."],
    ["suricata_keywords", "Tool (hunt2 only) that lists the rule keywords the installed Suricata 8.0.6 supports, with descriptions and documentation links."],
    ["Known-good traffic", "Traffic between internal hosts (59.166.0.0/24 clients to 149.171.126.0/24 servers), treated as normal on the basis of the dataset's published testbed description; the gate's reference."],
    ["Topology rule", "An AI rule that matches ordinary protocol activity from outside HOME_NET with no attack constraint (e.g. SMTP MAIL FROM, POP3 login). It scores well on UNSW-NB15 only because every external host there is an attacker."],
    ["Signature rule", "A rule keyed on attack content (exploit strings, traversal, format strings, injection)."],
    ["Behavioural rule", "A rule keyed on a rate or on protocol misuse (e.g. over-long fields, fuzzed file names, parser anomalies) rather than a fixed string."],
    ["Dataset-indicator rule", "A rule keyed on a string that identifies this laboratory rather than an attack technique (e.g. a test domain name)."],
    ["Instance rule / technique rule", "An instance rule matches one exploit attempt's exact payload (e.g. its filler bytes) and rarely fires again; a technique rule matches the property every attempt shares (e.g. any ../ traversal)."],
    ["Replay variance", "Two Suricata replays of the same capture with the same rules do not produce identical alerts, because thresholds and flow handling depend on timing."],
    ["Attributable gain", "Attack events matched by an AI-rule alert and by no other alert in the same replay."],
    ["Genuine gain", "Attributable gain counted from signature and behavioural rules only — topology and dataset-indicator rules excluded."],
    ["Content-detectable event", "An attack event in which the attacker sent application data in a matching flow, so a content rule could in principle see it."],
    ["Ever-detected event", "An attack event caught by at least one configuration run in this project (baseline, all-rules control or a genuine AI rule); a practical, circular ceiling."],
    ["Thinking mode / reasoning carry", "DeepSeek V4 Pro may return its reasoning in a separate reasoning_content field. Until a fix made during Experiment 3 the adapter discarded it, so the model's reasoning was not carried to the next turn; it now is."],
    ["ADS comment", "A comment above each hunt rule stating its goal, blind spots and expected false positives, after Palantir's Alerting and Detection Strategy framework."],
]
cur = Cursor(abbr._tbl)
cur.h1("Glossary of Project Terms")
cur.p("Terms coined or given a specific meaning in this project.", size=10, italic=True)
cur.table(abbr, GLOSSARY, 2, font=9, widths=[1.6, 4.6])
cur.caption("Table 0-1: Glossary of project terms", "Table")

# ---- Abstract
p = para("We introduce an agentic triage engine")
insert_after_text(p, "namely Claude Opus 5, DeepSeek V3, and DeepSeek V4 Pro.",
                  " It was then evaluated, unchanged, on a second dataset it had never been tuned for (UNSW-NB15), "
                  "and every AI-authored rule was scored against both datasets' ground-truth labels.")
strike(p, rtext(p)[rtext(p).index("The system generated 24"):],
       "On CIC-IDS2017 the model identified 13 of 14 labelled attack categories, and its rules raised the number of "
       "categories caught by at least one true-positive alert from 8 (stock ET Open alone) to 12. On the two noisiest "
       "captures, 99.4% of label-matched AI-rule alerts fell on attack flows, against 6.1% for the stock rules. On UNSW-NB15 "
       "the model identified 8 of 9 attack categories across six captures, and its rules raised event-level detection of "
       "TCP/UDP attacks from 9.2% to 15.5% without adding a single alert on a benign host. The evaluation also documents "
       "consequential model errors: deleting effective rules on a hallucinated claim, writing rules that do not load, and "
       "reading routine traffic as data exfiltration. A context experiment showed that the model identified attacks as broadly "
       "from alert events alone, but only full sensor context let it establish whether those attacks succeeded.")
append(para("Keywords:"), ", UNSW-NB15, ground-truth evaluation")

# ---- Introduction
insert_after_text(para("For this project, Suricata 8.0.6"), "(Sharafaldin, Habibi Lashkari & Ghorbani 2018)",
                  " and, for cross-dataset evaluation, the UNSW-NB15 dataset (Moustafa & Slay 2015)")
g2 = para("Measure the detection capability")
append(g2, " Both are measured against the datasets' ground-truth labels, including on a second dataset the system was never tuned for.")
g3 = _clone_para(g2._p, g2._p)
r = g3.add_run("Establish what context the model needs, by comparing triage given only alert events with triage given full sensor context (Experiment 1).")
r.font.color.rgb = RED
strike(para("Section IV explains how the triage engine"), "and shows some initial results.",
       "the results, and the cross-dataset evaluation on UNSW-NB15.")
append(para("The findings are analysed and discussed in Section V"),
       " It also presents the ground-truth evaluation of every AI-authored rule, the rule audit, the context experiment, and the threats to validity identified during evaluation.")
strike(para("A summary of the work done so far"), "done so far", "and its conclusions")

# ---- Literature review
append(para("The agentic paradigm is a stark contrast"),
       " The design follows the ReAct pattern, in which a language model interleaves reasoning with actions against an "
       "external environment and uses each observation to plan its next step (Yao et al. 2023), and builds on evidence "
       "that language models can learn when and how to call external tools (Schick et al. 2023).")
cur = Cursor(para("In a survey of deep learning techniques"))
cur.p("A known risk of generative models is hallucination: fluent, confident output that is not supported by the input "
      "or by fact (Ji et al. 2023). In a conventional chatbot this produces a wrong answer; in an agent that can write and "
      "delete detection rules it produces a wrong action. Section V documents a case of exactly this kind, which is why the "
      "system keeps a human in the loop for any change that reduces detection.")
lit_summary = [p for p in d.paragraphs if p.text.strip() == "Summary" and p.style.name == "Heading 2"][0]
cur = Cursor(lit_summary._p.getprevious())
cur.h2("Evaluation Datasets and Label Quality")
cur.p("Evaluating an intrusion detection system requires labelled traffic. Ring et al. (2019) survey the available "
      "network datasets and show that they differ widely in realism, labelling method and attack coverage, so results "
      "on a single dataset generalise poorly. CIC-IDS2017 (Sharafaldin, Habibi Lashkari & Ghorbani 2018) labels every "
      "flow produced by CICFlowMeter; UNSW-NB15 (Moustafa & Slay 2015, 2016) was generated with the IXIA PerfectStorm "
      "tool and lists each attack event with its endpoints, time and one of nine attack categories. Using both allows "
      "the approach to be tested beyond the dataset it was developed on.")
cur.p("Labels are not error-free. Engelen, Rimmer and Joosen (2021) identified flow-construction and labelling problems "
      "in CIC-IDS2017, and Lanvin et al. (2023) documented packet misordering, duplication and attacks that were performed "
      "but not correctly labelled. This matters for the present evaluation: where an AI-authored rule and the labels "
      "disagree, the disagreement has to be examined before it is counted as an error of the rule.")

strike(para("To evaluate the performance of LLM in autonomous IDPS rule generation"), "пред-prepared", "pre-prepared")
cur = Cursor(para("It turns out that the design of the tools is as important"))
cur.p("A hosted language model can only produce text. What makes it an agent is the set of tools the engine offers it: "
      "each tool is described to the model as a JSON schema (name, purpose, parameters), the model replies with a "
      "structured request to call one, and the engine — not the model — checks the request against the experiment "
      "profile, runs it and returns the result for the next turn (Figure 3-3). The model can therefore investigate, "
      "research, validate and write rules, but only through these 13 functions, each with its own limits (Table 3-2, "
      "Figure 3-8). Eight were built for the first CIC-IDS2017 triage; five were added for the UNSW-NB15 experiments.")
AGENT_TOOLS = [
    ["Tool", "What it does", "Safeguards", "Profiles"],
    ["count_alerts", "Alerts in an eve.json grouped by signature, most frequent first — the usual first step.", "Allowlisted paths only.", "All"],
    ["count_by", "Counts the values of any jq expression over eve.json (event types, IP pairs, protocol fields), in Python, so it works on NDJSON.", "Allowlisted paths; 120 s timeout.", "All"],
    ["query_eve_json", "Runs a jq filter over eve.json and returns matching events.", "150-line cap with a hint to aggregate; 60 s timeout.", "All"],
    ["read_file", "Reads a configuration, rule or log file.", "Only logs/, config/, rules/, data/pcaps/; labels, notes, transcripts and results refused; 150-line cap.", "All"],
    ["list_directory", "Lists files with sizes.", "Blocked paths hidden.", "All"],
    ["write_file / append_to_file", "Writes a detection rule file, or proposes a suppression.", "Only rules/generated/ and threshold.config; suppressions need human approval; hunt profiles: append only, own rule file only, and only rules that passed test_rule unchanged.", "All"],
    ["run_suricata", "Replays a capture with the profile's Suricata configuration into logs/<run>/, so the model can validate its rules.", "Profile's configuration only; 10-minute timeout.", "All"],
    ["search_rules", "Searches the rules actually loaded (message, references, content) — 'is this already covered?'", "Read-only.", "Plain, research, hunt, hunt2"],
    ["lookup_vulnerability", "Product, flaw type and description from a local copy of the NVD CVE database (2002–2016).", "Offline; refuses dataset or traffic-generator terms.", "Research, hunt, hunt2"],
    ["stack_values", "Counts a field's values and lists the rarest first — stack counting for hunting.", "Allowlisted paths; capped list.", "Hunt, hunt2"],
    ["test_rule", "Syntax check, replay with only the rule, replay with addresses widened to any → any; reports alerts by host role and a PASS/FAIL verdict per rule.", "Reports counts only, never labels; scratch output deleted after each test.", "Hunt, hunt2"],
    ["suricata_keywords", "Lists the rule keywords this Suricata build supports; exact names return the documentation link.", "Read-only.", "Hunt2"],
]
cur.table(table("Capture"), AGENT_TOOLS, 4, font=8, widths=[1.15, 2.6, 2.1, 0.95])
cur.caption("Table 3-2: The agent's tools — the only actions the model can take", "Table")
cur.figure("fig3-8_agent_tools.png", "Fig. 3-8 : The agent's toolkit grouped by purpose, with the engine-enforced safeguards", width=6.3)
strike(para("It turns out that the design of the tools is as important"),
       "aggregates in Python by using collections. Do not have to adhere to the NDJSON limitation as in Counter.",
       "aggregates in Python using collections.Counter, so it is not affected by the NDJSON limitation.")
strike(para("This architecture is important for two reasons."), "any tool that supports calling", "any model that supports tool calling")
# ---- Approach
cur = Cursor(para("Stage 3: Output:"))
cur.figure("fig3-4_safety_asymmetry.png", "Fig. 3-2 : Safety asymmetry — detection rules deploy automatically after validation; suppressions require human approval")
cur = Cursor(para("The operation of the loop is as follows."))
cur.figure("fig3-3_agentic_loop.png", "Fig. 3-3 : Agentic tool-calling loop — every interaction between the hosted model and the sensor passes through the engine and a validated tool")

replace_plain(para("Fig. 3-2 : Web UI screenshot"), "Fig. 3-2", "Fig. 3-4")
changes = para("Changes from Original Project Plan")
cur = Cursor(changes._p.getprevious())
cur.h2("Dataset Configuration and Evaluation Integrity")
cur.p([("Dataset abstraction. ", True), ("The first version of the system prompt hard-coded the CIC-IDS2017 network layout, and "
      "the model's rule-validation tool always used the CIC Suricata configuration. For the second dataset both were "
      "parameterised: each dataset now has its own network-layout statement, Suricata configuration (HOME_NET) and "
      "generated-rule file, selected per run, so that rules the model validates are tested under the correct network "
      "definition. The triage procedure, tools and model are otherwise unchanged.", False)])
cur.p([("Tool-access allowlist. ", True), ("An audit of the triage transcripts (Section V, Threats to Validity) found that "
      "earlier runs had listed the ground-truth directory, whose file names reveal the attack types, and that one Tuesday "
      "run had read the ground truth from the project's own notes. The tools now open only the directories an analyst at "
      "a sensor would use — logs/, config/, rules/ and data/pcaps/ — and refuse labels, project notes, earlier "
      "transcripts and results. No UNSW-NB15 run attempted to read the labels.", False)])
cur.p([("Alerts-only condition. ", True), ("For Experiment 1 the same engine can run in a mode in which every query is "
      "restricted to alert events: flow and application-layer events, protocol statistics and rules written under the "
      "full-context condition are unavailable to the model. This isolates the effect of context on triage quality.", False)])

plan_last = para("CIC-IDS2017 was finalized to set as a test environment")
item = _clone_para(plan_last._p, plan_last._p)
r = item.add_run("UNSW-NB15 was added as a second evaluation dataset at the supervisor's request (Week 9 meeting), to test "
                 "whether the approach generalises beyond the dataset on which it was developed.")
r.font.color.rgb = RED

# ---- Section IV: CIC results
replace_plain(para("IV. Execution and Preliminary Results"), "Execution and Preliminary Results", "Execution and Results")
append(para("This part explains the implementation of the triage engine"),
       " A second dataset, UNSW-NB15, was then evaluated in raw mode only (see Cross-Dataset Evaluation: UNSW-NB15).")
append(para("Claude authored two rules for the campaign level"),
       " Ground-truth replay (Section V) later showed that four of the five DeepSeek rules, including both stages of the "
       "hostbits chain, never fired on the Tuesday capture; only SID 9000004 (the Paramiko client fingerprint) fired, "
       "matching 574 SSH-Patator flows with no false positives.")
strike(para("Raw pass (2,310,105 alerts, DeepSeek V4 Pro)"),
       "which led the detector to miss 463 hits, hence V4 Pro rewrote the rule using raw TCP payload matching at depth:8",
       "so V4 Pro rewrote the rule using raw TCP payload matching at depth:8, after which it fired 463 times")
append(para("The model also conducted a forensic analysis on the Heartbleed"),
       " Of these, SID 7600101 can never fire in Suricata 8.0.6 because the TLS event it relies on is not registered, and "
       "the Heartbleed rule file was not loaded in any Wednesday replay. SIDs 7600102–7600103 were later found to fire on "
       "real exploit traffic in UNSW-NB15.")
strike(para("This capture (Thursday-WorkingHours in the dataset) includes"), "25,399", "25,406")
append(para("HTTP login brute force:"),
       " Ground-truth replay confirmed the gap: no stock alert matched any of the 1,507 labelled brute-force flows, "
       "whereas the AI rule SID 7600001 matched 8 of them with no false positives.")
strike(para("Reflected cross-site scripting:"), "this will be corrected in Experiment 2.",
       "the flow-level evaluation in Section V measures detection against the 652 labelled XSS flows directly.")
p = para("Data Staging:")
strike_all(p, "Data staging (retracted): the model reported 44 hex-named .txt uploads from .8 using the Tuesday "
              "credentials (iscxtap/1234). Ground-truth replay does not support this. The rule written for it (SID "
              "7600004) fired on uploads from every internal workstation on both Tuesday and Thursday, and every "
              "label-matched hit falls on flows labelled BENIGN. The uploads indicate routine simulated user activity; "
              "the account is most likely the testbed's ordinary FTP account, whose weak password the Tuesday attack happened to guess.")
append(para("Internal scanning:"),
       " The labels mark these flows BENIGN. Because CIC-IDS2017 is known to leave some performed attacks unlabelled "
       "(Lanvin et al. 2023), this is treated as a disputed label rather than a false positive.")
append(para("Six detection rules were written (SID 7600001-7600006)"),
       " On replay against the Thursday capture, SID 7600001 matched 8 labelled brute-force flows, SID 7600003 matched "
       "2 Infiltration flows (and 2 benign), SID 7600004 fired only on benign traffic, and SIDs 7600002, 7600005 and "
       "7600006 fail to parse in Suricata 8.0.6 (unknown keyword smb.command; malformed dcerpc.iface), so they never "
       "loaded. The model's own validation of these rules had replayed a small test capture, not the Thursday traffic.")
p = para("This capture (Friday-WorkingHours in the dataset)")
strike(p, "525", "263")
append(p, " The tuned log used for triage contained two appended Suricata runs, so the model analysed 525 alert events — every alert twice.")
ssh = para("SSH brute force: 526 flow records")
strike(ssh, rtext(ssh)[rtext(ssh).index("This traffic was fired"):],
       "SID 9500002, written by Claude for Tuesday, fired on this traffic. The label join (Section V) shows that all 79 of "
       "its label-matched Friday alerts fall on flows labelled PortScan, so this is the SSH phase of the port scan rather "
       "than a separate brute-force campaign.")
flood = para("HTTP GET flood :")
append(flood, " The AI rule written for this campaign (SID 9500003) was never loaded in any replay because its rule file "
              "was not listed in the Suricata configuration, so its effect could not be measured; the equivalent campaign "
              "rules SID 9600001 and its copy 9600003 matched 49 and 193 DDoS-labelled flows respectively.")
cur = Cursor(flood)
cur.p([("Botnet (ARES). ", True), ("In a later validation run on 21 September 2026, prepared for the Week 9 supervisor "
      "demonstration, DeepSeek V4 Pro found the ARES botnet that the interim report had listed as undetected: five internal "
      "hosts (.5, .8, .9, .14, .15) polling the C2 server 205.174.165.73:8080 with 666 GET /api/pop?botid=… requests and 70 "
      "POST /api/upload or /api/report requests, all with the python-requests user agent. No stock or custom alert fired on "
      "this traffic. The model wrote three rules (SID 9700001–9700003) that each fired five times on replay — once per "
      "infected host — and all 15 alerts match Bot-labelled flows. The transcript of this session was not exported, so "
      "the model's reasoning cannot be audited; the rules, their commentary and the validation logs are the evidence.", False)])

p = para("The AI triage engine detected 12 of 14")
strike(p, rtext(p)[:rtext(p).index("These fill in several coverage gaps")],
       "Across the four attack days the model identified 13 of the 14 labelled attack categories (DoS slowloris and DoS "
       "Slowhttptest were reported as a single campaign, and only Slowhttptest flows were matched by the resulting rules); only DoS GoldenEye "
       "(Wednesday, 10,293 labelled flows) was never named in a triage report. Bot/ARES, reported as undetected in the "
       "interim report, was found in the 21 September run. Across all CIC-IDS2017 sessions the model wrote 32 rule "
       "definitions (27 distinct detections once copies and superseded drafts are removed); Section V audits each of them. ")

t = table("Capture")
cell_strike(t.rows[0].cells[5], "Rules Retained", "Rule definitions")
cell_strike(row(t, "Tuesday").cells[3], "—", "1,842,712 (later replay)")
thu = row(t, "Thursday")
cell_strike(thu.cells[2], "25,399", "25,406")
cell_strike(thu.cells[4], ", data staging", "")
cell_strike(thu.cells[6], "SMB sweep, ", "")
cell_append(row(t, "Wednesday").cells[5], "; +2 deleted")
fri = row(t, "Friday")
cell_strike(fri.cells[2], "525", "263")
cell_append(fri.cells[4], ", Bot (ARES)")
cell_append(fri.cells[5], "; 11 incl. copies and ARES rules (App. D)")
cell_append(fri.cells[6], ", ARES botnet C2")
cur = Cursor(t._tbl)
cur.caption("Table 4-2: Execution summary — alert volumes, attack categories identified and AI-authored rule definitions per capture", "Table")
cur.p("Figure 4-2 compares alert volumes. Raw CIC-IDS2017 captures produce between 1.3 and 2.3 million alerts, most of "
      "them Suricata engine events such as invalid-checksum alerts; baseline suppression reduces this by three to four "
      "orders of magnitude. UNSW-NB15 raw captures produce fewer than a thousand alerts each, because the checksum "
      "artefact is specific to the CIC capture.")
cur.figure("fig4-2_alert_volume.png", "Fig. 4-2 : Alert volume per capture — CIC-IDS2017 tuned and raw passes, UNSW-NB15 raw (log scale)")

# ---- Section IV: UNSW-NB15
cur.h2("Cross-Dataset Evaluation: UNSW-NB15")
cur.p("At the supervisor's request (Week 9), the triage engine was evaluated on UNSW-NB15 (Moustafa & Slay 2015), "
      "generated with the IXIA PerfectStorm tool in the UNSW Canberra Cyber Range Lab as a mix of real normal activity "
      "and synthetic attacks in nine families: Analysis, Backdoor, DoS, Exploits, Fuzzers, Generic, Reconnaissance, "
      "Shellcode and Worms. Its ground truth (NUSW-NB15_GT.csv) lists every attack event with start and end time, "
      "endpoints, protocol and category. Six 2 GB capture files from the 17 February 2015 capture were used (files 1, 3, "
      "4, 5, 10 and 14; a seventh, file 27, was truncated during download and contained no ground-truth events). Together "
      "they contain 31,432 labelled attack events, 14,935 of them TCP or UDP, covering all nine categories.")
cur.p("The network layout was derived from the ground truth and the traffic itself: every attack originates in "
      "175.45.176.0/24 and targets 149.171.126.0/24, while 59.166.0.0/24 generates normal client traffic, so HOME_NET was "
      "set to the server and client ranges in a separate configuration. UNSW-NB15 has no benign-only day, so no "
      "Monday-style baseline could be built and all UNSW runs are raw. Stock ET Open was loaded together with the rules "
      "written on CIC-IDS2017, to test whether they transfer. Apart from the network-layout statement, the prompt, tools "
      "and model (DeepSeek V4 Pro) were unchanged. Table 4-3 summarises the six runs.")
cur.table(t, [
    ["Capture", "Raw alerts", "From attacker range", "Turns", "Duration", "Rules written", "Model validated its rules"],
    ["unsw-1", "997", "79%", "75", "12 min", "2", "Yes"],
    ["unsw-3", "893", "85%", "44", "10 min", "3", "Yes"],
    ["unsw-4", "625", "77%", "44", "33 min", "2", "Yes"],
    ["unsw-5", "905", "87%", "43", "111 min", "5", "Yes"],
    ["unsw-10", "799", "77%", "62", "9 min", "3", "No (replayed by the team)"],
    ["unsw-14", "854", "83%", "50", "41 min", "3", "Yes"],
], 7, font=9)
cur.caption("Table 4-3: UNSW-NB15 triage runs (DeepSeek V4 Pro, raw captures)", "Table")
cur.p("The alert stream is very different from CIC-IDS2017: 625–997 alerts per capture, 77–87% of them involving the "
      "attacker range. It is also sparse relative to the attacks: capture 3 alone contains 18,506 labelled attack events "
      "but produced 893 alerts, so the stock ruleset sees only a small part of the attack activity. Run duration varied "
      "from 9 to 111 minutes for a similar number of turns, which reflects API response times rather than task difficulty.")
cur.p("Figure 4-3 shows which ground-truth categories each run's findings correspond to, obtained by looking up the hosts "
      "and ports cited in each finding in the ground truth. Across the six runs the model identified eight of the nine "
      "categories; each run found four to seven. Some identifications were exact: the unsw-3 report names SQL Slammer "
      "worm propagation to 149.171.126.17:1434/UDP, which is the single Worms event in that capture, and outbound cmd.exe "
      "shell banners reported in unsw-1 and unsw-5 match labelled Backdoor events. Analysis (port scans, spam and HTML "
      "penetration) was never identified.")
cur.figure("fig4-3_unsw_findings_matrix.png", "Fig. 4-3 : Ground-truth categories identified by each UNSW-NB15 triage run")
cur.p("The six runs wrote 18 rules. All of them load and fire on replay, because the UNSW configuration listed the "
      "model's rule file from the outset (contrast the CIC rule audit in Section V). One run, unsw-10, skipped its own "
      "validation step; the team replayed its three rules, which fired 2, 4 and 1 times, all on attacker traffic. Four "
      "rules duplicate existing ones: two re-author the CIC Heartbleed rules with a new message, and two repeat earlier "
      "UNSW rules even though the model had read the rule file first. Rules transfer across captures: with every rule "
      "loaded, 13 of the 15 rules written on other captures fired on capture 14.")
cur.p("The CIC-authored Heartbleed rules SID 7600102–7600103 fired on all six captures, only on attacker traffic, and "
      "matched 495 ground-truth attack events, mostly in the Generic category. Five of the six runs judged these alerts "
      "true positives. The unsw-3 run judged them stale false positives — the traffic was a large upload, the opposite "
      "of a Heartbleed leak — and proposed suppressing both rules. The ground truth labels that exact flow "
      "(175.45.176.0 → 149.171.126.18:2444) as a Cisco Unified Communications Manager heap-overflow exploit, which is "
      "precisely why it was a large upload. Because suppressions require approval, the proposal was not applied. Had it "
      "been applied automatically, the model would have blinded the sensor to a real exploit — direct evidence for the "
      "safety asymmetry described in Section III.")
append(para("The CIC-authored Heartbleed rules SID 7600102–7600103 fired"),
       " A later rule-by-rule classification (Section V, Attribution and the Topology Trap) qualifies the first part of this "
       "paragraph: both rules fire on any outside host that opens five TLS connections within five minutes. In UNSW-NB15 "
       "every outside host is an attacker, so their matches show where the attackers are, not that the CIC rules "
       "recognise an attack technique; they are not evidence that CIC-authored rules transfer to UNSW-NB15.")

# ---- Section V
v = para("V. Analysis and Discussion")
v.style = d.styles["Heading 1"]
append(para("The analysis of this section looks at various aspects"),
       " It then reports the ground-truth evaluation of every AI-authored rule on both datasets, the rule audit, the "
       "context experiment, and threats to validity.")
insert_after_text(para("For the credential brute-force capture (Tuesday)"), "No attack was detected by one model and not by the other.",
                  " This agreement is weaker evidence than it appears. The only DeepSeek V3 run that completed the Tuesday "
                  "triage (triage-2026-09-04-03-07-23.txt) read the Tuesday ground truth from the project's notes before "
                  "concluding; the two earlier V3 runs exhausted their 30-turn limit before the count_by tool existed. "
                  "Claude's run was a CLI session that was not logged, so the same check cannot be made. Neither result can "
                  "be shown to be independent of the labels.")
mag = para("The most important practical finding is that the approach is model-agnostic.")
strike(mag,
       "The most important practical finding is that the approach is model-agnostic. Both made similar findings in Tuesday's capture, where both model families were evaluated, indicating that the power is in how the model is used with the tool, not what it can do.",
       "Model-agnosticism is a property of the design — one prompt, one tool set and one loop behind a provider adapter — "
       "rather than a result this evaluation establishes. The one head-to-head comparison is compromised (above), and "
       "every other capture was triaged by a single model. Wednesday offers only indirect evidence: V3 on the tuned pass "
       "and V4 Pro on the raw pass identified the same attacks from different alert sets. A controlled comparison — two "
       "models, one capture, identical locked-down environments — remains future work.")
mc = table("Metric")
cell_append(row(mc, "Captures triaged").cells[3], ", UNSW-NB15 (6 captures)")
cell_append(row(mc, "Turns (Friday)").cells[3], " (tuned input duplicated; see Section IV)")
cell_append(row(mc, "Rules written").cells[3], "; later 6 ARES rules (CIC-IDS2017) and 18 UNSW-NB15 rules")
add_row(mc, ["Turns (UNSW-NB15)", "—", "—", "43–75 per capture (6 runs)"])
cell_append(row(mc, "Key findings (Tuesday)").cells[2], " — completed run read ground truth from project notes (see Threats to Validity)")
cell_append(row(mc, "Turns (Tuesday tuned)").cells[2], " (label-informed run; see Threats to Validity)")
strike(mag,
       "but this will be left to the final report.",
       "Token usage is recorded per turn in every transcript (for example, 2.7–6.5 million input tokens per UNSW-NB15 "
       "run), but each provider's pricing at the time of the runs was not captured, so a monetary comparison is left as "
       "future work.")

rt = table("Attack")
cell_strike(row(rt, "HTTP login brute force").cells[2], "Authored (SID 7600001); replay validation pending (Experiment 2)",
            "8 alerts, all on labelled brute-force flows (SID 7600001)")
cell_strike(row(rt, "Reverse shell").cells[2], "Authored (SID 7600003); replay validation pending (Experiment 2)",
            "4 alerts: 2 on Infiltration flows, 2 on benign (SID 7600003)")
smb = row(rt, "SMB lateral sweep")
cell_strike(smb.cells[2], "Authored (SID 7600002); replay validation pending (Experiment 2)", "Rule fails to load (SID 7600002)")
cell_strike(smb.cells[3], "New coverage", "None")
add_row(rt, ["SSH brute force (Tuesday)", "60 SSH-Patator flows matched (1.0%)", "574 alerts, all on SSH-Patator flows (SID 9000004)", "1.0% → 28.4% of flows"])
add_row(rt, ["ARES botnet C2 (Friday)", "0", "15 alerts, all on Bot flows (SID 9700001–9700003)", "New detection"])
add_row(rt, ["FTP “data staging” (Thursday)", "—", "768 alerts, none on attack flows (SID 7600004)", "False-positive rule"])
p = para("The improvements can be divided into three categories.")
strike(p, "Second, new coverage for non-detected attack categories in the stock rule set – see the following: HTTP brute force (rules written, not replayed); Hulk flood (rules validated, not replayed); SMB lateral sweep (rules written, not replayed); Reverse shell (rules validated, not replayed); FAKEVERB (rules validated, not replayed).",
       "Second, new coverage where the stock ruleset had none: FAKEVERB, the Hulk flood, the HTTP login brute force, the "
       "reverse shell and the ARES botnet, each now confirmed by ground-truth replay (Table 5-2); the SMB lateral-sweep "
       "rule does not load and provides no coverage.")

cur = Cursor(p)
cur.h2("Ground-Truth Evaluation (Experiment 2)")
cur.p([("Method. ", True), ("Every alert was joined to the datasets' labels. For CIC-IDS2017 an alert matches a labelled "
      "flow if it shares the flow's 5-tuple (in either direction) and its timestamp falls within the flow's lifetime plus "
      "120 seconds either side; the slack is needed because the label timestamps have one-minute resolution, use a "
      "12-hour clock without AM/PM, and are in Atlantic Daylight Time. For UNSW-NB15 an alert matches a ground-truth event "
      "if it shares its IPs, ports and protocol within the event's time window (±2 seconds). UNSW results are headlined "
      "for TCP/UDP events only: other protocols carry no ports, IP-only matching is sensitive to the tolerance, and "
      "TCP/UDP results were identical at ±2 and ±10 seconds. Suricata's own engine and decoder events (SIDs "
      "2200000–2299999) are excluded from the stock baseline, because in raw CIC captures the invalid-checksum event fires "
      "on nearly every packet and would count every flow as detected. Tuesday and Thursday were replayed with every CIC "
      "rule loaded; the Wednesday and Friday captures had been removed from the working environment to free storage for "
      "UNSW-NB15, so their AI rules are scored from the validation logs recorded during triage. The scripts are in "
      "src/eval/ of the repository.", False)])
cur.p([("Detection on CIC-IDS2017. ", True), ("Figure 5-1 shows, for each labelled attack, the share of flows matched by at "
      "least one alert. The AI rules add detection where the stock ruleset had little or none: SSH-Patator rises from "
      "1.0% to 28.4%, DoS Slowhttptest from 0% to 9.1%, and web brute force, Bot and DoS Hulk from 0% to between 0.4% and "
      "1.0%. The low absolute values for volumetric attacks are a property of the metric: the AI rules are deliberately "
      "campaign-level and fire once per threshold window, while the labels count every flow — 231,073 of them for DoS "
      "Hulk. Category coverage and precision describe these rules better. DoS GoldenEye and DoS slowloris are detected by "
      "neither rule set; the model's 'Slowloris' rule in fact matches flows labelled DoS Slowhttptest, a confusion of "
      "two tools that its own rule text reveals.", False)])
cur.figure("fig5-1_cic_recall.png", "Fig. 5-1 : CIC-IDS2017 — labelled attack flows matched by stock ET Open and by stock plus AI-authored rules")
cur.p([("Detection on UNSW-NB15. ", True), ("Across the six captures the AI rules raise event-level detection of TCP/UDP "
      "attacks from 9.2% to 15.5%, a 68% relative increase (Figure 5-2). Reconnaissance rises from 18.7% to 36.2% and "
      "Exploits from 9.9% to 19.1%. Alerts on traffic with no attacker involved did not increase (749 stock, 746 with AI "
      "rules): every alert of every AI rule involves the attacker range. The absolute values are low even for the stock "
      "rules because the generator launches thousands of one-off exploit attempts, many with no signature in any ruleset.", False)])
cur.figure("fig5-2_unsw_recall.png", "Fig. 5-2 : UNSW-NB15 — TCP/UDP ground-truth attack events matched by stock ET Open and by stock plus AI-authored rules")
cur.p([("Precision. ", True), ("Of the stock rules' label-matched alerts on the two noisiest captures (Wednesday and Friday "
      "raw), only 6.1% fall on attack flows; for the AI rules the figure is 99.4% (Figure 5-3). Over all four days the "
      "stock rules reach 81.2%, because Tuesday and Thursday stock alerts are mostly on real attacks, and the AI rules "
      "78.0%. Almost all of the AI rules' false positives come from a single rule, the FTP 'data staging' rule SID "
      "7600004; excluding it and the disputed internal-sweep rule SID 7600007 gives 99.6%.", False)])
cur.figure("fig5-3_precision.png", "Fig. 5-3 : Share of label-matched alerts that fall on attack flows — stock ET Open versus AI-authored rules")
cur.p([("Category coverage. ", True), ("Figure 5-4 summarises coverage as the number of labelled attack categories with at "
      "least one true-positive alert, and the number the model named in its findings. On CIC-IDS2017 the stock rules "
      "cover 8 of 14 categories, the stock and AI rules together 12, and the model's findings 13 (counting DoS slowloris, "
      "which the model reported together with DoS Slowhttptest). On UNSW-NB15 all three "
      "reach 8 of 9, with Analysis missed by all; there the AI rules add depth within categories rather than new "
      "categories.", False)])
cur.figure("fig5-4_category_coverage.png", "Fig. 5-4 : Attack categories covered by stock rules, by stock plus AI-authored rules, and by the model's triage findings")
cur.p([("Comparison with human-authored rules. ", True), ("ET Open is written and maintained by human experts, so the "
      "comparison above is a comparison of AI-authored rules with human-authored ones on the same traffic. On time, "
      "Scarfone and Mell (2007) describe manual rule development as taking hours to days; each triage run in this project "
      "covered an entire capture and produced validated rules in 9 to 111 minutes. A direct comparison with a human "
      "analyst performing the same triage was not carried out and is proposed as future work.", False)])

cur.h2("Rule Audit")
cur.p("Every rule the models authored was traced to its session and checked for whether it loads, whether it was ever "
      "replayed, and whether it fired (Table 5-3, Figure 5-5; the full list is in Appendix D). The contrast between the "
      "datasets is the main result. All 18 UNSW-NB15 rules load and fire. Of the 32 CIC-IDS2017 rule definitions, 16 fired "
      "on replay; three fail to load, one loads but can never fire, the model deleted two, four Tuesday rules never fired "
      "when replayed, and six were never replayed at all.")
cur.p("The difference is environmental. During the CIC-IDS2017 triage the Suricata configuration listed only three of the "
      "ten generated rule files, and the model is not permitted to edit it. New rule files were therefore never loaded "
      "by the model's own validation runs, which reported success while testing nothing. The model worked around this in "
      "two sessions by copying its rules, under new SIDs, into a file that was loaded — the origin of SIDs 9600003–9600004 "
      "and of the ARES rules inside Claude's Tuesday rule file. For UNSW-NB15 the configuration listed the model's rule "
      "file from the outset, and every rule was genuinely validated. An agent's self-validation is only as good as the "
      "environment it validates in.")
cur.table(rt, [
    ["Rule status", "CIC-IDS2017", "UNSW-NB15"],
    ["Fired on replay", "16", "18"],
    ["Replayed, never fired", "4", "0"],
    ["Never replayed (file not loaded)", "6", "0"],
    ["Loads, can never fire", "1", "0"],
    ["Fails to load", "3", "0"],
    ["Deleted by the model", "2", "0"],
    ["Total rule definitions", "32", "18"],
    ["of which copies or duplicates", "2", "4"],
    ["of which superseded drafts", "3", "0"],
], 3, font=9, widths=[2, 1, 1])
cur.caption("Table 5-3: Audit of AI-authored rule definitions", "Table")
cur.figure("fig5-5_rule_audit.png", "Fig. 5-5 : Status of every AI-authored rule definition")

append(para("This is a practical compromise."),
       " On UNSW-NB15 the distinction largely disappears: raw captures produced 625–997 alerts each, because the "
       "invalid-checksum alerts that dominate raw CIC-IDS2017 volume are an artefact of that capture, not of raw mode itself.")
strike_all(para("In the brute force triage (Tuesday), Claude"),
           "SID 9500002, written by Claude for Tuesday's SSH brute force, fired on Friday traffic from the same attacker; "
           "all 79 of its label-matched Friday alerts fall on PortScan flows, so it generalised to the SSH phase of the "
           "port scan rather than to a second brute-force campaign. Stronger evidence comes from UNSW-NB15: rules written "
           "on one capture fired on the others (13 of 15 on capture 14). Two CIC Heartbleed rules also matched 495 UNSW "
           "attack events, but they are topology-style rules (Section V), so that match is not evidence of transfer.")
strike_all(para("Likewise, the credentials used in the credential brute force"),
           "The interim report also described a cross-capture correlation: Tuesday's cracked FTP credentials "
           "(iscxtap/1234) reused for Thursday data staging. The ground-truth evaluation does not support it (Section IV): "
           "identical uploads come from every workstation on both days and are labelled benign. The model constructed a "
           "plausible narrative from routine activity.")
p = para("The importance of this episode lies in two aspects.")
strike(p, "After being deleted by V4 Pro, the total number of AI-authored rules is therefore 24, of which 22 remain in the repository.",
       "The complete rule inventory is given in the Rule Audit and Appendix D.")
cur = Cursor(p)
cur.p("The ground-truth evaluation and later runs exposed further errors of the same general kind — confident output "
      "that was not checked against reality:")
cur.p([("Rules that do not work. ", True), ("Three Thursday rules use keywords Suricata 8.0.6 rejects, and one Heartbleed "
      "rule depends on an event that does not exist. The model reported all four as written and, in the Thursday case, "
      "as validated — its validation run had replayed a small test capture.", False)])
cur.p([("Misread traffic. ", True), ("The FTP 'data staging' finding turned routine uploads into exfiltration, and the "
      "'Slowloris' rule matches Slowhttptest traffic.", False)])
cur.p([("Skipped procedure. ", True), ("One UNSW run wrote rules without validating them, and one read its rule file and "
      "still re-wrote two existing rules.", False)])
cur.p([("Inconsistent verdicts. ", True), ("The same model reached opposite verdicts on the same evidence in different runs: "
      "five UNSW runs judged the Heartbleed rules correct and one proposed suppressing them, and two runs split on whether "
      "a shellcode signature was a false positive.", False)])
cur.p([("Duplicated input. ", True), ("The Friday tuned triage analysed an eve.json file containing two appended Suricata "
      "runs, so any count it quoted from that run is doubled.", False)])

summary_v = [p for p in d.paragraphs if p.text.strip() == "Summary" and p.style.name == "Heading 2"][-1]
cur = Cursor(summary_v._p.getprevious())
cur.h2("Context Experiment (Experiment 1)")
cur.p("The research question asks what context the model needs. Experiment 1 compares the six full-context UNSW-NB15 "
      "runs, in which the model could query every event type, with runs on the same captures in which it could see "
      "alert events only (Section III). Three captures are repeated in the alerts-only condition (1, 3 and 10), and "
      "both conditions are scored with the same ground-truth method.")
cur.table(rt, [
    ["Measure (captures 3, 1, 10)", "Full context", "Alerts only"],
    ["Categories identified per run (main)", "3, 6, 5", "7, 5, 5"],
    ["Categories identified, union of runs (of 9)", "6", "7"],
    ["TCP/UDP GT events covered by findings", "1,117 of 6,753 (16.5%)", "1,892 of 6,753 (28.0%)"],
    ["Outcome statements: total (evidence-backed)", "53 (52)", "15 (9)"],
    ["Rules written / fired on replay", "8 / 8", "10 / 9"],
    ["Rule alerts matching GT events", "37 of 123 (30%)", "462 of 652 (71%)"],
    ["Rule alerts on non-attacker hosts", "0", "0"],
    ["TCP/UDP detection: stock + CIC → with condition's rules", "8.8% → 8.9%", "8.8% → 12.2%"],
    ["Turns", "44, 75, 62", "57, 48, 60"],
    ["Duration", "10, 12, 9 min", "10, 7, 8 min"],
    ["Input tokens (three runs)", "12.9 million", "9.0 million"],
], 3, font=9, widths=[2.2, 1, 1])
cur.caption("Table 5-4: Experiment 1 — full sensor context versus alerts only (DeepSeek V4 Pro, UNSW-NB15)", "Table")
cur.p("The result runs against the natural expectation that more context produces better triage. Without context the model was not "
      "worse at finding attacks: across the three captures it identified seven categories against six, and its findings "
      "covered 28.0% of TCP/UDP ground-truth events against 16.5%. Its rules added more detection (8.8% to 12.2%, against "
      "8.8% to 8.9%), largely because two of them target portmapper sweeps, while the full-context runs on these captures "
      "happened to write narrower rules for individual compromises. Neither condition's rules fired on a benign host.")
cur.p("Context changed the depth of the triage rather than its breadth. With every event type available, the model "
      "established what each attack achieved — 59 password guesses answered '230 Login successful', 2.25 MB returned by "
      "a Heartbleed-vulnerable server, the byte counts of a reverse shell — and made 53 such outcome statements, all but "
      "one backed by evidence. Restricted to alerts, it produced broader, signature-organised reports with 15 outcome "
      "statements, six of which state that success cannot be confirmed from alert data alone. For an analyst the second "
      "question — did the attack succeed — decides the response, so context is what makes the triage actionable rather "
      "than what makes it complete (Figure 5-6).")
cur.figure("fig5-6_experiment1.png", "Fig. 5-6 : Experiment 1 — breadth of detection and depth of outcome evidence with full sensor context and with alerts only")
cur.p("Three caveats limit the result. Each condition was run once per capture, so run-to-run variation, which Section V "
      "shows to be substantial, is not separated from the effect of context. 'Alerts only' is not context-free: Suricata "
      "alert records carry their own per-flow byte and packet counters, which the alerts-only runs used. One alerts-only "
      "rule (SID 7700004) re-authored the CIC Heartbleed rule, as the full-context unsw-5 run had, so the ten rules are "
      "nine new detections; its alerts duplicate the baseline and do not contribute to the gain. And the findings "
      "measure rewards broad reports, which favours the enumerative style the alerts-only condition produced. The "
      "outcome-statement count is an automatic pattern match over the final reports and is indicative rather than exact. "
      "The designed context bundle (source history, asset context, rule history) was not built and remains future work.")
cur.h2("Threats to Validity")
cur.p([("Label leakage. ", True), ("The transcript audit found that the Thursday and Friday CIC-IDS2017 runs listed the "
      "ground-truth directory, whose file names name the attacks (for example '…Afternoon-DDos' and '…PortScan'); their "
      "attempts to read the files returned only the first rows, all benign. One Tuesday DeepSeek V3 run read the Tuesday "
      "ground truth from the project's notes (triage-2026-09-04-03-07-23.txt). The two earlier V3 runs did not read the "
      "notes but did not complete (turn limit), and Claude's run was not logged, so no completed Tuesday triage can be "
      "shown to be independent of the labels. The Tuesday rules are unaffected — ground-truth replay scored them (SID "
      "9000004: 574 of 574 alerts on SSH-Patator flows; SID 9500001: 185 of 185 on FTP-Patator) — but the Tuesday triage "
      "finding itself must be treated as label-informed, although the interim report presented it as independent. "
      "Access is now restricted (Section III), and no UNSW-NB15 run attempted it.", False)])
cur.p([("Label quality and matching. ", True), ("CIC-IDS2017 labels contain documented errors (Engelen, Rimmer & Joosen "
      "2021; Lanvin et al. 2023). About 300 alerts from the Wednesday slow-HTTP rules, on long, slow connections, and 334 "
      "from the FTP rule SID 7600004 could not be joined to any labelled flow. The matching rules are heuristics; their tolerances and exclusions are stated above so that the results can "
      "be reproduced.", False)])
cur.p([("Incomplete replay. ", True), ("The CIC-IDS2017 capture files were removed from the working environment to free "
      "storage for the UNSW-NB15 evaluation. The Tuesday and Thursday captures were re-obtained and replayed; the Wednesday "
      "and Friday rules are scored from the validation logs recorded during triage, and six rules whose files were never "
      "loaded could not be scored.", False)])
cur.p([("Sample size and provenance. ", True), ("Most conditions were run once, so run-to-run variation — visible in the "
      "split verdicts — is not quantified. The ARES session transcript was not exported, and there is no human-analyst "
      "baseline performing the same task.", False)])

p = para("The analysis shows the AI triage engine generates rules")
strike(p, "The two model families yielded similar results on Tuesday, when they were both run, indicating that the approach is not model-specific.",
       "The Tuesday model comparison is compromised by label leakage, so model-agnosticism remains a property of the design rather than a demonstrated result.")
strike(p, "Two attack categories were not observed (DoS GoldenEye and Bot/ARES), indicating that the system is not 100% complete and that additional research is needed to determine why these attack categories were not observed.",
       "Only DoS GoldenEye was never identified; Bot/ARES was found in a later run. Scored against ground truth, the AI "
       "rules raised CIC-IDS2017 category coverage from 8 to 12 of 14 and UNSW-NB15 TCP/UDP event detection from 9.2% to "
       "15.5%, with 99.4% precision on the noisiest captures — but the same evaluation found invalid rules, a false-positive "
       "rule and misread traffic that the model had reported with confidence.")

# ---- VI Summary
p = para("The triage engine completed the analyst workflow on all four attack days.")
strike(p, rtext(p)[rtext(p).index("It matched 12 of the 14"):],
       "The model identified 13 of the 14 labelled CIC-IDS2017 attack categories (all but DoS GoldenEye) and 8 of the 9 "
       "UNSW-NB15 categories (all but Analysis), on a dataset it had never been tuned for.")
strike_all(para("During all of the sessions, 24 AI-created detection rules"),
           "The models wrote 32 rule definitions on CIC-IDS2017 and 18 on UNSW-NB15. Scored against ground truth, the AI "
           "rules raised CIC-IDS2017 category coverage from 8 to 12 of 14 categories and UNSW-NB15 TCP/UDP event detection "
           "from 9.2% to 15.5%, never alerting on a benign UNSW host; on the noisiest CIC captures 99.4% of their "
           "label-matched alerts fell on attack flows, against 6.1% for the stock rules. The rule audit also found three "
           "rules that do not load, one that can never fire, one false-positive rule, and two effective rules deleted by "
           "the model.")
append(para("The entire process of detection is rule-based"),
       " In one UNSW-NB15 run the model proposed suppressing rules that were detecting a real exploit; because the proposal "
       "required approval, the sensor was not blinded.")
p = para("There are three findings that have relevance beyond")
strike(p, "There are three findings", "Several findings")
strike(p, "Third, early evidence suggests that rules produced by AI can be generalized across captures, which should be formally tested against the ground-truth labels.",
       "Third, rules written on one UNSW-NB15 capture fired on others; the apparent transfer of CIC-authored rules to "
       "UNSW-NB15 rests on two topology-style rules and is withdrawn (Section V). Against the strengthened baseline, "
       "rules keyed to a single exploit instance did not transfer, while technique-level hunt rules did.")
append(p, " Finally, an agent's self-validation is only as good as its environment: where the configuration did not load the "
          "model's rule files, its validation runs reported success while testing nothing.")
cur = Cursor(p)
cur.p([("Answer to the research question. ", True), ("The evidence supports a split answer. For triage, yes: with "
      "sensor-available context a large language model carries out the alert-handling workflow of a rule-based IDS end to "
      "end, identifying 13 of 14 CIC-IDS2017 and 8 of 9 UNSW-NB15 attack categories and establishing whether attacks "
      "succeeded. Experiment 1 shows what the context buys: alert events alone were enough to identify attacks as broadly, "
      "but flow and application-layer context is what allowed the model to establish outcomes — the question that decides "
      "an analyst's response. For extending detection, the answer is partial: the model's rules clearly extend stock ET "
      "Open, but against a human baseline strengthened the way a detection engineer would strengthen it, triage-driven "
      "rule writing added only a fraction of a percentage point of genuine detection — counted from events no other rule "
      "caught, with topology rules removed. Replicating detection-engineering practice, with the model's reasoning carried "
      "across turns, added 1.2 to 1.5 points that held on untouched traffic with no false alarms on benign captures: real, "
      "but modest against the roughly 70% of attack events every ruleset still misses, and confounded with a mid-round "
      "fix to the model adapter; a second run of the same workflow with a keyword reference added a similar, slightly "
      "smaller gain from largely different attacks. The model cannot replace the analyst unsupervised: its errors are confident and "
      "consequential, so rule changes that reduce detection must stay under human approval and every authored rule needs "
      "independent replay.", False)])

# ---- VII Future Work
append(para("This section describes the work that remains to be done"),
       " Experiment 2 has since been completed and Experiment 1 carried out in reduced form (Section V); the text below "
       "records their status and the remaining work.")
p = para("Experiment 1: Does the context make a difference?")
insert_after_text(p, "Experiment 1: Does the context make a difference?",
                  " Status: a reduced form (alerts only versus full sensor context) is reported in Section V; the full context bundle below remains future work.")
strike_all(para("Experiment 2: Quantitative evaluation of rules."),
           "Experiment 2: Quantitative evaluation of rules. Completed; see Section V, Ground-Truth Evaluation. Remaining: "
           "re-running the Wednesday and Friday rules against their captures so that every rule is scored from a single "
           "consistent replay.")
p = para("Experiment 3: Convergence testing.")
append(p, " Carried out in revised form as repeated AI rule-writing rounds on the strengthened UNSW-NB15 baseline "
          "(Sections IV and V): instead of alert volume on benign traffic, each round measures the detection the AI rules "
          "add. Remaining: the hunt condition's captures 1 and 10, and a technique-level variant of the hunt procedure.")
cur = Cursor(p)
cur.p([("Human analyst baseline. ", True), ("A team member triaging one UNSW-NB15 capture by hand, timed and with the same "
      "tools, and scored with the same scripts, would allow a direct comparison of human and model performance.", False)])
cur.p([("Controlled model comparison. ", True), ("Two providers triaging the same capture in the locked-down environment "
      "(Section III), to test the model-agnosticism claim properly.", False)])
cur.p([("Environment-aware validation. ", True), ("The rule-validation tool should load any rule file the model has just "
      "written, so that self-validation always tests the new rules (see Rule Audit).", False)])

# ---- References (alphabetical insertion, red)
REFS = {
    "Denning, DE 1987": ["Engelen, G, Rimmer, V & Joosen, W 2021, 'Troubleshooting an intrusion detection dataset: the CICIDS2017 case study', in 2021 IEEE Security and Privacy Workshops (SPW), pp. 7–12. https://doi.org/10.1109/SPW53761.2021.00009"],
    "Hadi, HJ, Yasmin, R": ["Ji, Z, Lee, N, Frieske, R, Yu, T, Su, D, Xu, Y, Ishii, E, Bang, YJ, Madotto, A & Fung, P 2023, 'Survey of hallucination in natural language generation', ACM Computing Surveys, vol. 55, no. 12, art. 248. https://doi.org/10.1145/3571730"],
    "Ko, C, Ruschitzka": ["Lanvin, M, Gimenez, PF, Han, Y, Majorczyk, F, Mé, L & Totel, É 2023, 'Errors in the CICIDS2017 dataset and the significant differences in detection performances it makes', in Risks and Security of Internet and Systems (CRiSIS 2022), Lecture Notes in Computer Science, vol. 13857, Springer, pp. 18–33. https://doi.org/10.1007/978-3-031-31108-6_2"],
    "Liao, HJ": ["Moustafa, N & Slay, J 2015, 'UNSW-NB15: a comprehensive data set for network intrusion detection systems (UNSW-NB15 network data set)', in 2015 Military Communications and Information Systems Conference (MilCIS), Canberra, pp. 1–6. https://doi.org/10.1109/MilCIS.2015.7348942",
                 "Moustafa, N & Slay, J 2016, 'The evaluation of network anomaly detection systems: statistical analysis of the UNSW-NB15 data set and the comparison with the KDD99 data set', Information Security Journal: A Global Perspective, vol. 25, no. 1–3, pp. 18–31."],
    "Proofpoint 2026": ["Ring, M, Wunderlich, S, Scheuring, D, Landes, D & Hotho, A 2019, 'A survey of network-based intrusion detection data sets', Computers & Security, vol. 86, pp. 147–167. https://doi.org/10.1016/j.cose.2019.06.005"],
    "Scarfone, K & Mell": ["Schick, T, Dwivedi-Yu, J, Dessì, R, Raileanu, R, Lomeli, M, Hambro, E, Zettlemoyer, L, Cancedda, N & Scialom, T 2023, 'Toolformer: language models can teach themselves to use tools', in Advances in Neural Information Processing Systems, vol. 36."],
    "Vaswani, A": ["Yao, S, Zhao, J, Yu, D, Du, N, Shafran, I, Narasimhan, K & Cao, Y 2023, 'ReAct: synergizing reasoning and acting in language models', in Proceedings of the 11th International Conference on Learning Representations (ICLR 2023)."],
}
for after, refs in REFS.items():
    cur = Cursor(para(after))
    for ref in refs:
        cur.p(ref, template=T_REF)

# ---- Appendix B corrections (AI declaration)
decl = table("Reference to one or more AI tools")
out_cell = decl.rows[1].cells[1]
for text in ["[Correction: Wednesday had two passes, not three — DeepSeek V3 tuned (SID 3000001–3000003) and DeepSeek V4 Pro raw (SID 3000004 and the Heartbleed rules). See Section IV.]",
             "[Addition: later outputs include the Thursday and Friday triage (DeepSeek V4 Pro), the ARES botnet rules (21 September) and six UNSW-NB15 triage runs; all transcripts are in the repository.]"]:
    pp = out_cell.add_paragraph()
    rr = pp.add_run(text); rr.font.color.rgb = RED
def cell_para(cell, contains):
    hits = [p for p in cell.paragraphs if contains in rtext(p)]
    assert len(hits) == 1, f"{len(hits)} cell paragraphs contain {contains!r}"
    return hits[0]


strike(cell_para(out_cell, "Wednesday Triage Output (DeepSeek V3, 3 passes)"), "(DeepSeek V3, 3 passes)",
       "(two passes: DeepSeek V3 tuned, DeepSeek V4 Pro raw)")
append(cell_para(out_cell, "Full triage log: triage-2026-09-04-03-07-23.txt"),
       " [Note: this run read the Tuesday ground truth from the project notes; see Section V, Threats to Validity.]")
refl = decl.rows[2].cells[1]
strike(cell_para(refl, "(47-94x better)"), "vs 2-4 on the Emerging Threats rule (47-94x better)",
       "vs 3 on the Emerging Threats rule (62× better)")
strike(cell_para(refl, "syntax checked with Suricata -T"), "and passed with p.",
       "; three of them (SID 7600002, 7600005, 7600006) fail to load in Suricata 8.0.6 (Section V, Rule Audit).")
append(cell_para(refl, "Both led to the same predictions"),
       " [Qualification: the completed DeepSeek V3 run read the Tuesday ground truth from project notes; see Section V, Threats to Validity.]")
for text in ["[Check: the sentence stating that DeepSeek was 10× more expensive contradicts the cost figures that follow (Claude is the more expensive model).]",
             "[Addition: Claude Code was also used to write the evaluation scripts (src/eval/), produce the figures, and draft sections of this final report; the team reviewed all output.]"]:
    pp = refl.add_paragraph()
    rr = pp.add_run(text); rr.font.color.rgb = RED

# ---- Appendix D: rule audit
cur = Cursor(d.paragraphs[-1])
cur.h1("Appendix D: AI-Authored Rule Audit")
cur.p("Every AI-authored rule definition, its authoring session, load status and replay evidence. CIC evidence: alerts, "
      "and label-matched alerts on attack / benign flows. UNSW evidence: alerts, ground-truth-matched alerts, and captures "
      "(of six) on which the rule fired. Generated from docs/results/rule_audit.csv.", size=9)
rows = [["SID", "Data", "Author / session", "Status", "Replay evidence", "Notes"]]
for r_ in csv.DictReader(open(DOCS / "results/rule_audit.csv")):
    ev = ""
    if r_["cic_alerts"]:
        ev = f"CIC: {r_['cic_alerts']} alerts ({r_['cic_on_attack']} attack / {r_['cic_on_benign']} benign)"
    if r_["unsw_alerts"]:
        ev += ("; " if ev else "") + f"UNSW: {r_['unsw_alerts']} alerts, {r_['unsw_gt_matched']} GT-matched, {r_['unsw_pcaps_fired']}/6 captures"
    note = r_["notes"] + (f" Duplicate of {r_['duplicate_of']}." if r_["duplicate_of"] else "")
    rows.append([r_["sid"], r_["dataset"], r_["author_session"], r_["load_status"], ev or "—", note.strip() or "—"])
cur.table(t, rows, 6, font=7, widths=[1.15, 0.75, 2.5, 1.05, 2.15, 2.4])
cur.caption("Table D-1: Inventory of AI-authored rule definitions", "Table")

# ================================================================ OCTOBER ADDITIONS
# Strengthened UNSW baseline, AI rounds (Experiment 3), the hunt condition and the hold-out. Every number below is
# read from docs/results/*.json, the rule files or the hunt transcript (src/eval/rounds.py, extra_rulesets.py,
# make_figures_v2.py).
import json
import re as _re

RES = DOCS / "results"
_J = lambda f: json.loads((RES / f).read_text())
XR, CTRL, RND, GATE, CLS = (_J("extra_rulesets.json")["unsw"], _J("baseline_control.json"), _J("rounds.json"),
                            _J("test_rule_gate.json"), _J("round_rule_classes.json"))
ROOT_ = DOCS.parent
TOT = sum(XR["tcpudp_events"].values())
pct = lambda a, b: f"{100 * a / b:.1f}%"
pts = lambda a, b: f"{100 * a / b:.2f}"
layer = lambda k: sum(XR["layers"][k]["detected"].values())
BL, AO = CTRL["baseline"], CTRL["allon"]
HO = RND["baseline-holdout"]


def _sids(path):
    return [int(x) for x in _re.findall(r"^alert.*?\bsid\s*:\s*(\d+)", path.read_text(), _re.M)]


def _classes(cond):
    c = {}
    for sid in _sids(ROOT_ / f"rules/generated/unsw/rounds_{cond}.rules"):
        k = CLS.get(str(sid), {}).get("class", "unclassified")
        c[k] = c.get(k, 0) + 1
    return c


HUNT_RUNS = [("3", "Before fix", ROOT_ / "triage-2026-10-04-05-48-19-unsw-v2-hunt.txt"),
             ("1 (first attempt)", "Before fix", ROOT_ / "transcripts_failed/triage-2026-10-04-09-20-29-unsw-v2-hunt.txt"),
             ("1", "After fix", ROOT_ / "triage-2026-10-04-10-03-09-unsw-v2-hunt.txt"),
             ("10", "After fix", ROOT_ / "triage-2026-10-04-10-14-15-unsw-v2-hunt.txt"),
             ("3 (hunt2)", "After fix", ROOT_ / "triage-2026-10-04-11-18-22-unsw-v2-hunt2.txt"),
             ("1 (hunt2)", "After fix", ROOT_ / "triage-2026-10-04-11-29-16-unsw-v2-hunt2.txt"),
             ("10 (hunt2)", "After fix", ROOT_ / "triage-2026-10-04-11-48-49-unsw-v2-hunt2.txt")]


def _run_facts(path):
    t = path.read_text(errors="replace")
    g = lambda pat: _re.search(pat, t, _re.M).group(1).strip()
    return {"turns": g(r"^Turns:\s+(\d+)"), "dur": g(r"^Duration:\s+(.+)$"), "tok": g(r"^Tokens:\s+([\d,]+) input"),
            "tests": t.count("[TOOL CALL] test_rule"), "appends": t.count("[TOOL CALL] append_to_file"),
            "thinking": t.count("[THINKING]"), "report": "FINAL TRIAGE REPORT" in t}


HF = {k: _run_facts(pth) for k, _, pth in HUNT_RUNS}
HUNT_T = HUNT_RUNS[0][2]
_ht = HUNT_T.read_text()
H_TURNS = _re.search(r"^Turns:\s+(\d+)", _ht, _re.M).group(1)
H_DUR = _re.search(r"^Duration:\s+(.+)$", _ht, _re.M).group(1).strip()
H_TOK = _re.search(r"^Tokens:\s+([\d,]+) input", _ht, _re.M).group(1)
H_TESTS = _ht.count("[TOOL CALL] test_rule")
H_STACK = _ht.count("[TOOL CALL] stack_values")
H_CALLS = len(_re.findall(r"^\[TOOL CALL\]", _ht, _re.M))
EX_FAIL, EX_PASS = GATE["examples"][0], GATE["examples"][1]

# ---- Abstract
append(para("We introduce an agentic triage engine"),
       f" A second phase strengthened the human baseline the way a detection engineer would — re-enabling rule families "
       f"that ship disabled, chosen from the services seen in the traffic — which raised UNSW-NB15 TCP/UDP detection from "
       f"{pct(layer('ET Open'), TOT)} to {pct(layer('all extra + re-enabled'), TOT)}. Against that baseline, three AI "
       f"conditions were compared: two triage-driven conditions added genuine detection of only "
       f"+{pts(RND['plain-r2']['ai_new_genuine'], RND['plain-r2']['tcpudp'])} and "
       f"+{pts(RND['research-r2']['ai_new_genuine'], RND['research-r2']['tcpudp'])} percentage points, most of their apparent "
       f"gain coming from rules that match the dataset's network layout rather than attack behaviour, while a condition "
       f"that replicates detection-engineering practice with an anti-topology test gate added "
       f"+{pts(RND['hunt-r1']['ai_new_genuine'], RND['hunt-r1']['tcpudp'])} points, and "
       f"+{pts(RND['hunt-r1-holdout']['ai_new_genuine'], RND['hunt-r1-holdout']['tcpudp'])} on untouched hold-out captures "
       f"with no alert on benign-only traffic. That gain coincides with a fix to how the model's reasoning is carried across "
       f"turns, made during the round, and the two effects cannot yet be separated. Adding a reference of supported rule "
      f"keywords removed rule-loading failures but did not raise detection (+{pts(RND['hunt2-r1-holdout']['ai_new_genuine'], RND['hunt2-r1-holdout']['tcpudp'])} "
      f"points on the hold-out): different runs of the same procedure found largely different attacks. Most missed attacks "
      f"carried data, so the remaining gap is unwritten signatures rather than undetectable traffic. The frozen baseline alone detected "
       f"{pct(HO['base_det'], HO['tcpudp'])} of hold-out attack events.")

# ---- Introduction: structure of report
append(para("Section IV explains how the triage engine"),
       " It also reports the strengthened UNSW-NB15 baseline and the AI rule-writing rounds run against it (Experiment 3).")

# ---- Literature review: detection-engineering practice and LLM rule generation
cur = Cursor(para("Labels are not error-free."))
cur.h2("Detection Engineering Practice and LLM-Generated Rules")
cur.p("In practice, detection rules are produced by a detection-engineering lifecycle rather than written ad hoc: a "
      "hypothesis about attacker behaviour is turned into a rule, the rule is tested against traffic known to contain the "
      "behaviour and against traffic known to be benign, reviewed, deployed and tuned. Palantir's Alerting and Detection "
      "Strategy (ADS) framework formalises this as a template that every detection must complete before release, with "
      "sections including the goal, the technical context, blind spots and assumptions, expected false positives and "
      "validation (Palantir 2017). Atkinson (2020) argues that rules should target the abstract capability an attacker "
      "needs rather than the surface features of a particular tool, because tools change while the underlying technique "
      "does not. Threat hunting supplies the hypotheses: stack counting, or long-tail analysis, counts every value of a "
      "field and examines the rare ones, which needs no statistical model and no training period (Dragos 2023).")
cur.p("Several recent systems use large language models to generate intrusion detection rules. FALCON generates Snort and "
      "YARA rules from cyber-threat-intelligence reports and filters them through syntactic, semantic and performance "
      "validators (Mitra et al. 2025). GRIDAI uses several cooperating agents to decide whether an attack sample is new, "
      "in which case a rule is written, or a variant of a known attack, in which case an existing rule is repaired (Li et "
      "al. 2025). GenTI benchmarks models on IDPS rule generation (Hadi, Yasmin & Shoker 2026). RuleAutoPilot is the "
      "closest to this project: an agentic pipeline that writes Suricata rules from malware traffic, filters known-benign "
      "flows first, and accepts a rule only if it loads, fires on the source traffic and stays silent on a benign corpus; "
      "this execution-grounded validation raised its F1 score from 0.443 to 0.539 (Rehman, Piplai & Kantarcioglu 2026). "
      "A user study with ten domain experts found that experts treat LLM-written network rules as drafting and "
      "verification aids rather than autonomous generators, citing low specificity and logic errors in 12% of cases "
      "(di Filippo et al. 2026).")
cur.p("These systems start from labelled malicious samples or threat intelligence. This project asks a different "
      "question: whether an agent working from unlabelled sensor traffic, with no access to ground truth, can add "
      "detection to a strong human-tuned baseline — and it borrows the validation idea from RuleAutoPilot and the "
      "procedure from detection-engineering practice to test it (Section III).")

# ---- Approach: profiles, hunt condition, gate
cur = Cursor(para("Alerts-only condition."))
cur.h2("Tools and Software")
cur.p("Table 3-1 lists every tool and library the project used, its version and what it was used for. All are open source "
      "or open access, except the two hosted model APIs, which the system calls but does not depend on (Section III, "
      "Provider Adapter Pattern).")
TOOLS = [
    ["Tool / library (version)", "Role in this project"],
    ["Suricata 8.0.6 (OISF)", "The rule-based IDS: offline pcap replay (suricata -r), rule loading and syntax checks (-T), eve.json output, keyword list for suricata_keywords."],
    ["suricata-update 1.3.8", "Downloads and merges the ET Open ruleset into rules/suricata.rules."],
    ["ET Open (Proofpoint)", "Community ruleset (52,647 rules); the stock baseline for both datasets."],
    ["Snort Community, Stamus lateral, PT Open", "Additional open rulesets evaluated for UNSW-NB15 baseline v2; disabled ET and Snort families re-enabled by service."],
    ["jq 1.7", "Every query the agent runs over eve.json (query_eve_json, count_by, stack_values)."],
    ["tshark / editcap 4.2.2 (Wireshark)", "Checking capture dates and timestamps, slicing captures for fast iteration."],
    ["Python 3.12", "Triage engine, tools, provider adapters, evaluation and figure scripts (src/)."],
    ["FastAPI 0.141 + Uvicorn 0.52", "Web server that streams the agent's reasoning and tool calls to the browser via Server-Sent Events."],
    ["openai 3.7 SDK → DeepSeek V4 Pro / V3", "OpenAI-compatible client for DeepSeek, the model used for almost all runs."],
    ["anthropic 1.2 SDK → Claude Opus 5", "Client for Claude, used for the early CIC-IDS2017 triage."],
    ["Local NVD knowledge base (SQLite)", "Offline copy of the NVD CVE database (2002–2016) behind lookup_vulnerability; no live web access."],
    ["Agent tools (src/tools.py)", "count_alerts, count_by, query_eve_json, read_file, write_file, append_to_file, run_suricata, list_directory; "
                                   "per profile: search_rules, lookup_vulnerability, stack_values, test_rule, suricata_keywords."],
    ["matplotlib 3.11 + CairoSVG 2.9", "All charts (matplotlib) and diagrams (hand-written SVG rendered to PNG) in this report."],
    ["python-docx 1.2, pptxgenjs 4.0", "Building this report and the presentation from the results files."],
    ["Ubuntu 24.04 on WSL 2, Git", "Development environment and version control (one repository, four contributors)."],
]
cur.table(abbr, TOOLS, 2, font=8.5, widths=[2.0, 4.4])
cur.caption("Table 3-1: Tools and software used", "Table")
cur.h2("Experiment Profiles")
cur.p("As conditions multiplied, each was defined as a named profile: the dataset, the Suricata configuration, the single "
      "rule file the model may write to, the tool set, the prompt, and the files the model may not open (Figure 3-5). The "
      "web interface, the command-line runner and the unattended batch runner all select a profile by name, and every "
      "transcript records it. A profile used in a scored run is frozen; a change creates a new profile, so that results "
      "can always be traced to the exact set-up that produced them. The web interface gained a profile selector next to "
      "the model selector, filtered to the profiles of the selected run's dataset.")
cur.figure("fig3-5_experiment_profiles.png", "Fig. 3-5 : Experiment profiles — one named, frozen bundle of configuration, prompt and tools per condition (the UNSW v1 profile, which predates profiles, is omitted)", width=6.3)
cur.h2("The Hunt Condition: a Detection-Engineering Workflow")
cur.p("Following the supervisor's advice to look at how detection engineers work in practice and replicate it with the "
      "agent, a third rule-writing condition was built around the lifecycle described in Section II (Figure 3-6). The "
      "triage conditions start from alerts, so the model only ever investigates traffic that some rule already fired on. "
      "The hunt procedure starts from the gaps instead: (1) map which protocols carry traffic but few alerts; (2) stack "
      "the attacker-controlled content fields of those protocols — URLs, user agents, FTP and SMTP commands, DNS names, "
      "SSH client versions, parser anomaly events — rare values first, without pivoting on IP addresses; (3) form a "
      "hypothesis, checking whether a loaded rule already covers it and looking up the vulnerability; (4) write the rule "
      "with an ADS-style comment stating its goal, blind spots and expected false positives; (5) test it; (6) save it.")
cur.p("Two tools were added. stack_values returns the values of any field rarest first, with the number of distinct "
      "values — the existing aggregation tool listed the most common values first and its output cap cut off exactly the "
      "long tail a hunter needs. test_rule checks a candidate rule's syntax, replays a capture with only that rule, then "
      "replays it again with the rule's addresses and ports widened to any → any, and reports the alerts of each version "
      "by direction (Figure 3-7). If the widened rule fires between internal hosts, its precision came from the source "
      "address rather than from the behaviour it claims to detect, and the verdict is FAIL; a rule that raises no alerts "
      f"also fails. Each test takes about {GATE['replay_seconds']} seconds on a 2 GB capture.")
cur.p("Traffic between internal hosts is treated as known-good on the basis of the dataset's published testbed "
      "description, in which two of the three servers generate normal traffic and one generates the attacks (Moustafa & "
      "Slay 2015; Fraunhofer FKIE 2026). This is documented topology, not per-event ground truth, and the tool reports "
      "counts by host role only. The engine enforces the gate: in this profile it refuses any write except an append to "
      "the profile's rule file, and refuses any rule that has not passed test_rule in exactly the form being saved. The "
      "hunt prompt also omits the attacker range that the triage prompts state, because a real detection engineer does "
      "not know it; the hunt condition therefore differs from the triage conditions in both procedure and context.")
cur.figure("fig3-6_hunt_workflow.png", "Fig. 3-6 : The hunt condition — the detection-engineering lifecycle as the agent's procedure, with an engine-enforced test gate", width=6.3)
cur.figure("fig3-7_test_rule_gate.png", "Fig. 3-7 : test_rule — a topology rule fails when widened to any → any; a behavioural rule passes (capture 3)", width=6.3)
cur.p("A fourth condition, hunt2 (profile unsw-v2-hunt2), is identical to the hunt condition except for one further tool. "
      "suricata_keywords lists the rule keywords the installed Suricata 8.0.6 supports, searched by name or description, "
      "and for an exact name returns its description and documentation link. It was added after the hunt transcripts "
      "showed the model guessing keywords that do not exist in this version (for example smb.filename) and falling back "
      "to raw-byte regular expressions. Hunt2 writes to its own rule file with its own SID range and cannot open the "
      "hunt condition's rules or logs, so the difference between the two conditions measures the tool.")

plan_last2 = para("UNSW-NB15 was added as a second evaluation dataset")
for txt in ["The UNSW-NB15 baseline was strengthened before further AI rounds, by enabling rule families that ET Open and "
            "Snort ship disabled, selected from the services seen in the traffic, so that the AI is compared with the "
            "strongest human baseline available rather than with an untuned ruleset.",
            "A hunt condition replicating detection-engineering practice was added after the supervisor advised looking at "
            "real-world practice, and round results are now credited only for attack events that no other rule detected."]:
    item = _clone_para(plan_last2._p, plan_last2._p)
    rr = item.add_run(txt); rr.font.color.rgb = RED
    plan_last2 = item

# ---- Section IV: strengthened baseline and AI rounds
cur = Cursor(para("The CIC-authored Heartbleed rules SID 7600102–7600103 fired"))
cur.h2("Challenges of UNSW-NB15")
cur.p("UNSW-NB15 differs from CIC-IDS2017 in ways that shaped every later design decision. Table 4-9 collects the "
      "challenges met, what each would have done to the results if ignored, and how the project handled it.")
CHAL = [
    ["Challenge", "Effect if ignored", "How it was handled"],
    ["No benign-only day", "No Monday-style tuning or suppressions possible", "All UNSW runs are raw; the baseline was strengthened by selecting rule families by service instead"],
    ["Every external host is an attacker", "Rules for ordinary activity from outside ('topology rules') score perfectly but would fail on a real network", "Every AI rule classified by its text; genuine gain counts signature and behavioural rules only; test_rule gate in the hunt profiles"],
    ["No internal POP3, SIP or SMB traffic", "The gate cannot test rules on those protocols against known-good traffic", "Stated as a limitation; benign-only hold-out captures used as the only check"],
    ["Generator varies every attempt (IXIA PerfectStorm)", "Rules for one exploit instance fire once and never again", "Instance and technique rules distinguished; transfer measured on captures no rule was written on"],
    ["Low signature coverage", "ET Open as shipped detects 9.2% of TCP/UDP attack events", "Baseline strengthened to 25.7%; detectability analysis shows most missed events carry data"],
    ["Event-level ground truth", "Alerts cannot be joined by flow ID", "Join on endpoints, ports, protocol and time (±2 s); headline on TCP/UDP events only"],
    ["22 January ground truth covers 11:00–14:00 UTC only", "Hold-out captures outside the window contain no labelled attacks", "Captures 25 and 50 kept as a false-alarm check; captures 3 and 6 added, chosen by time only"],
    ["Both days number files from 1; Wireshark shows local time", "17 February captures appear as 18 February; easy to mix up the days", "Every capture verified by its first-packet timestamp; hold-out kept in its own folder"],
    ["Truncated and large captures", "Capture 27 truncated; 1–2 GB files; stalled downloads", "Capture 27 excluded; downloads verified and re-run"],
    ["10 Snort rules reference an undefined variable", "They fail to load in every run", "Identical across all configurations, so comparisons are unaffected"],
    ["Replays are not repeatable", "Comparing two replays counts timing noise as gain (+82 vs +6 for the hunt round)", "Gains attributed within a single replay"],
    ["Data sent without the TCP PSH flag", "Payload cannot be inferred from flags", "Content-detectable estimated from byte counts"],
    ["Suricata normalises URLs", "Encoded traversal rules on http.uri match nothing", "The agent learned through the gate to use http.uri.raw"],
]
cur.table(t, CHAL, 3, font=8, widths=[1.7, 2.2, 2.6])
cur.caption("Table 4-9: Challenges of UNSW-NB15 and how they were handled", "Table")
cur.h2("Strengthening the UNSW-NB15 Baseline")
cur.p("The comparisons so far set the AI rules against ET Open as shipped. A detection engineer's first step with a "
      "sensor that misses most attacks would be to tune the rules already available, so the baseline was strengthened "
      "before any further AI rounds. Four further open rulesets were evaluated (Snort Community, Stamus lateral-movement, "
      "PT Open and an Nmap ruleset), and the rule families that ET Open and Snort ship disabled were re-enabled, selected "
      "by the services seen under attack in the eve.json traffic profile — never from the labels. Table 4-4 and Figure 4-4 "
      "show each step on the six development captures.")
rows = [["Configuration", "TCP/UDP events detected", "Detection", "Alerts"]]
for name, key in [("ET Open as shipped", "ET Open"), ("+ Snort Community", "ET Open + Snort Community"),
                  ("+ Stamus lateral", "ET Open + Stamus lateral"), ("+ PT Open", "ET Open + PT Open"),
                  ("+ Nmap scans", "ET Open + Nmap scans"), ("+ all extra rulesets", "ET Open + all extra"),
                  ("+ disabled ET families (selected)", "all extra + ET disabled (selected)"),
                  ("+ disabled Snort families (selected)", "all extra + Snort disabled (selected)"),
                  ("Baseline v2: all selected families", "all extra + re-enabled")]:
    rows.append([name, f"{layer(key):,} of {TOT:,}", pct(layer(key), TOT), f"{XR['layers'][key]['alerts']:,}"])
cur.table(rt, rows, 4, font=9, widths=[2.4, 1.4, 0.9, 0.9])
cur.caption("Table 4-4: Strengthening the UNSW-NB15 baseline (six development captures)", "Table")
cur.figure("fig4-4_baseline_ladder.png", "Fig. 4-4 : UNSW-NB15 TCP/UDP detection as rulesets and disabled rule families are added", width=6.3)
cur.p(f"Additional rulesets add almost nothing; re-enabling the selected disabled families nearly triples detection, from "
      f"{pct(layer('ET Open'), TOT)} to {pct(layer('all extra + re-enabled'), TOT)}. A control run enabled every disabled "
      f"rule: detection rose to {pct(AO['det'], AO['tcpudp'])}, but alerts on hosts with no attacker involved rose from "
      f"{BL['no_attacker']:,} to {AO['no_attacker']:,} (Figure 4-5) — the selection gives up a few points of detection "
      f"for {AO['no_attacker'] / BL['no_attacker']:.0f} times less noise. The Nmap ruleset was dropped because it degraded "
      "precision on CIC-IDS2017 without improving UNSW-NB15. The result, baseline v2, is frozen and contains human-written "
      f"rules only. Replays are not perfectly repeatable — Suricata's thresholds depend on packet timing — so the same "
      f"configuration scored {pct(BL['det'], BL['tcpudp'])} in the later replay used for the AI rounds.")
cur.figure("fig4-5_baseline_control.png", "Fig. 4-5 : Selected families versus enabling every disabled rule — detection and alerts on non-attacker hosts", width=6.0)
cats = sorted(BL["tcpudp_by_cat"], key=lambda c: -BL["tcpudp_by_cat"][c])
cp_ = lambda c: pct(BL["detected_by_cat"].get(c, 0), BL["tcpudp_by_cat"][c])
cur.p(f"Even the strengthened baseline misses most attack events in every category (Figure 4-6): Exploits {cp_('Exploits')}, "
      f"Fuzzers {cp_('Fuzzers')}, Reconnaissance {cp_('Reconnaissance')}, and Generic — "
      f"{BL['tcpudp_by_cat']['Generic']:,} events — only {cp_('Generic')}. Most missed events are one-off attempts whose "
      "content varies from attempt to attempt, which matters for what any rule author, human or AI, can add.")
cur.figure("fig4-6_category_ceiling.png", "Fig. 4-6 : Baseline v2 detection by UNSW-NB15 attack category", width=6.0)

cur.h2("AI Rounds on the Strengthened Baseline (Experiment 3)")
cur.p("Experiment 3 asks whether the agent can add detection to baseline v2. Three conditions were run with DeepSeek V4 "
      "Pro, each with its own profile, configuration and rule file so that no condition could see another's rules: plain "
      "triage with the search_rules tool (does a loaded rule already cover this?); research, which adds the local NVD "
      "vulnerability lookup; and hunt, the detection-engineering workflow of Section III. In each round the model wrote "
      "rules on captures 3, 1 and 10 in turn, every round's rules were loaded for the next, and all six development "
      "captures were then replayed and scored. Gains are credited only for TCP/UDP attack events matched by an AI-rule "
      "alert and by no other alert in the same replay (Section V explains why). Table 4-5 summarises the rounds.")
rows = [["Round", "Rules (fired)", "AI-rule alerts", "Matching an attack", "On non-attacker hosts", "Attributable gain", "Genuine gain"]]
for key, label in [("plain-r1", "Plain R1"), ("plain-r2", "Plain R2"), ("research-r1", "Research R1"),
                   ("research-r2", "Research R2"), ("hunt-r1", "Hunt R1"), ("hunt2-r1", "Hunt2 R1")]:
    r_ = RND[key]
    rows.append([label, f"{r_['rules_written']} ({r_['rules_fired']})", f"{r_['ai_alerts']:,}", pct(r_["ai_gt"], r_["ai_alerts"]),
                 str(r_["ai_noattacker"]), f"+{r_['ai_new']:,} (+{pts(r_['ai_new'], r_['tcpudp'])})",
                 f"+{r_['ai_new_genuine']} (+{pts(r_['ai_new_genuine'], r_['tcpudp'])})"])
cur.table(t, rows, 7, font=8, widths=[1.3, 0.9, 0.9, 0.9, 0.9, 1.3, 1.1])
cur.caption("Table 4-5: AI rounds on baseline v2 — events and percentage points of the 14,935 TCP/UDP attack events; rules counted over both rounds", "Table")
rows = [["Capture", "Reasoning carried", "Turns", "Duration", "Input tokens", "test_rule calls", "Rules saved / report"]]
for cap, fix, _ in HUNT_RUNS:
    f_ = HF[cap]
    saved = {"3": "7", "1 (first attempt)": "0", "1": "9", "10": "9", "3 (hunt2)": "9", "1 (hunt2)": "16", "10 (hunt2)": "7"}[cap]
    rows.append([cap, "No" if fix == "Before fix" else "Yes", f_["turns"], f_["dur"], f_["tok"], str(f_["tests"]),
                 f"{saved} / {'yes' if f_['report'] else 'no — turn limit'}"])
cur.table(t, rows, 7, font=8, widths=[1.1, 0.9, 0.6, 0.8, 1.0, 0.8, 1.3])
cur.caption("Table 4-6: Hunt and hunt2 runs (DeepSeek V4 Pro, web interface)", "Table")
cur.p(f"The hunt round was run through the web interface with the new profile selector (Table 4-6). On capture 3 the "
      "model mapped coverage, concentrated on HTTP as the protocol with the most external traffic and attacker-controlled "
      "fields, and found rare values that pointed to specific exploits the baseline did not detect: the D-Link router "
      "backdoor user agent (CVE-2013-6026), three HP OpenView Network Node Manager CGI attacks, a Cisco Secure ACS "
      "overflow, a vulnerable password-change CGI and a PHP webshell drop. Its seven rules all passed the gate, one after a "
      "correction.")
cur.p("The first attempt on capture 1 failed in a revealing way. Its rules passed test_rule, but in the remaining turns the "
      "model re-tested rules that had already passed, re-checked coverage it had already established, never saved anything "
      "and reached the 100-turn limit; the transcript contained tool calls but no reasoning at all. Checking each layer in "
      "turn — engine, server, browser, then the raw API — located the cause: DeepSeek V4 Pro was answering in its thinking "
      "mode, returning its reasoning in a separate reasoning_content field with an empty content field, and the provider "
      "adapter read only content. The model's reasoning was therefore neither logged nor sent back with the next turn, "
      "so it began every turn without its own plan. The adapter now streams the reasoning to the interface and the "
      "transcript and returns it with each turn; the hunt profile's turn budget was also raised to 150 (the fixed runs "
      f"used {HF['1']['turns']} and {HF['10']['turns']} turns, so the limit did not bind). With the fix, capture 1 finished "
      f"on its own in {HF['1']['turns']} turns and capture 10 in {HF['10']['turns']}, each with a full report and the "
      "model's reasoning recorded on every turn.")
cur.p("The rules written after the fix are of a different kind: instead of single exploit attempts they target techniques "
      "— path traversal in its raw, overlong-UTF-8 and encoded-backslash forms, cross-site scripting and PHP code in URIs "
      "and user agents, format strings in HTTP, FTP and SMTP — and two behaviours: an over-long SIP INVITE URI and SMB file "
      "names padded with fuzzing characters. The model again dropped candidates it judged unreliable: randomised POP3 and "
      "SIP logins and SMTP spam as indistinguishable from legitimate external users, and an LDAP enumeration whose only "
      "distinguishing string was specific to this laboratory. Table 4-7 lists all 25 rules.")
cur.p(f"The hunt2 runs, all with the reasoning fix, took {HF['3 (hunt2)']['turns']}, {HF['1 (hunt2)']['turns']} and "
      f"{HF['10 (hunt2)']['turns']} turns and saved 32 rules. The model used the keyword tool on every capture — 24 lookups "
      "in all — and none of its rules failed to load, against two load failures in the hunt condition's capture 10. "
      "Its rules use the protocol buffers the tool listed (ftp.command_data, ldap.request.dn, dns.query.name and a parser "
      "event, app-layer-event:smb.duplicate_negotiate) rather than raw bytes. Two of the 32 are not genuine: an LDAP "
      "modify-DN request from outside HOME_NET (topology) and an LDAP bind keyed on this laboratory's domain string "
      "(dataset indicator) — the first non-genuine rules the hunt procedure produced.")
rows = [["SID", "Rule (model's message)", "Goal (model's ADS comment)"]]
goal = None
for line in (ROOT_ / "rules/generated/unsw/rounds_hunt.rules").read_text().splitlines():
    if line.startswith("# Goal:"):
        goal = line.split("|")[0].replace("# Goal:", "").strip()
    m = _re.search(r'msg:"([^"]+)".*sid:(\d+)', line)
    if m:
        rows.append([m.group(2), m.group(1), goal or "—"])
cur.table(rt, rows, 3, font=8, widths=[0.8, 2.6, 2.8])
cur.caption("Table 4-7: Rules written in the hunt condition (captures 3, 1 and 10); every rule passed test_rule before it was saved", "Table")

# ---- Section V: attribution, topology, hunt analysis, hold-out
ctx = para("Context Experiment (Experiment 1)")
cur = Cursor(ctx._p.getprevious())
cur.h2("Attribution and the Topology Trap")
hr_ = RND["hunt-r1"]
cur.p([("Crediting the right rules. ", True), ("The first scoring of the AI rounds compared a fresh replay with the "
      "AI rules against the stored baseline replay. Because Suricata's threshold and flow logic depends on timing, two "
      "replays of the same capture with the same rules do not produce identical alerts, and the difference was counted as "
      f"gain: for the hunt round this method reported +{hr_['full_det'] - hr_['base_det']} events, of which only "
      f"{hr_['ai_new']} were matched by a hunt rule. All rounds were therefore re-scored by attribution — an event counts "
      "only if an AI-rule alert matches it and no other alert in the same replay does (Figure 5-7).", False)])
cur.p([("Topology rules. ", True), ("Every AI rule was then classified by its text as signature (attack content), "
      "behavioural (a rate or a protocol misuse), dataset-indicator (a string that identifies this testbed), or topology: "
      "ordinary protocol activity from outside HOME_NET with no attack constraint, such as an SMTP MAIL FROM, a POP3 login, "
      "a SIP REGISTER or an FTP login. In UNSW-NB15 every external host is an attacker, so a topology rule scores perfectly "
      "here and would alert on every legitimate external user of a real network. Figure 5-8 shows the composition by "
      "condition.", False)])
pc, rc_, hc = _classes("plain"), _classes("research"), _classes("hunt")
p2, r2 = RND["plain-r2"], RND["research-r2"]
cur.p(f"Most of the apparent gain was topology. Plain round 2 added +{pts(p2['ai_new'], p2['tcpudp'])} points of "
      f"attributable detection, but only +{pts(p2['ai_new_genuine'], p2['tcpudp'])} from signature and behavioural rules; "
      f"{pc.get('topology', 0)} of its {sum(pc.values())} rules are topology rules. The research condition wrote "
      f"{rc_.get('topology', 0)} topology rules of {sum(rc_.values())} and reached the largest genuine gain, "
      f"+{pts(r2['ai_new_genuine'], r2['tcpudp'])} points of the two triage-driven conditions. Their genuine gains differ "
      "by a few dozen events, too small to rank them. The hunt condition wrote "
      f"{hc.get('topology', 0)} topology rules and added +{pts(hr_['ai_new_genuine'], hr_['tcpudp'])} points, and the hunt2 "
      f"condition +{pts(RND['hunt2-r1']['ai_new_genuine'], RND['hunt2-r1']['tcpudp'])} — the only gains clearly above the "
      "noise (following subsections).")
cur.figure("fig5-7_rounds_attribution.png", "Fig. 5-7 : AI-round gains under the old metric, by attribution, and with topology rules removed", width=6.3)
cur.figure("fig5-8_rule_classes.png", "Fig. 5-8 : Classes of AI-authored rules by condition", width=6.0)

cur.h2("The Detection-Engineering Workflow")
cur.p(f"The hunt condition changed the kind of rule the agent wrote. All {sum(hc.values())} of its rules are content "
      f"signatures for named vulnerabilities; none is a topology rule; {pct(hr_['ai_gt'], hr_['ai_alerts'])} of their "
      f"alerts match a labelled attack and {hr_['ai_noattacker']} fall on hosts with no attacker involved. The gate behaved "
      f"as designed: on capture 3 the topology example fails because, widened, it matches "
      f"{EX_FAIL['widened']['int->int']:,} times between internal hosts, while the traversal example raises "
      f"{EX_PASS['widened']['ext->int']} alerts either way. The gate has a structural blind spot: it can only test "
      "protocols that internal hosts also use, and in UNSW-NB15 no internal host uses POP3, SIP or SMB (Figure 5-9).")
cur.figure("fig5-9_gate_coverage.png", "Fig. 5-9 : Protocol records by source role on capture 3 — the gate can only test protocols used by internal hosts", width=6.0)
UN = _J("rounds_unseen_dev.json")
cur.p(f"Whether the rules transfer depends on when they were written (Figure 5-10). The seven rules from capture 3, "
      "written before the reasoning-carry fix, each fired exactly once, on capture 3: several key on the exact filler of "
      "one exploit attempt — 'Logout+aaaa', 'displayWidth+1AAAA' — rather than on the property that makes it an overflow. "
      "In Atkinson's (2020) terms they detect the tool's surface, not the capability, and UNSW-NB15's generator launches "
      "each exploit with its own payload. The 18 rules written after the fix target techniques and behaviours, and most "
      "fire on captures they were never written on. Together the 25 rules added "
      f"+{hr_['ai_new_genuine']} attack events (+{pts(hr_['ai_new_genuine'], hr_['tcpudp'])} points); on development "
      f"captures 4, 5 and 14, on which no condition wrote rules, the hunt rules added +{UN['hunt-r1']['pts']:.2f} points "
      f"against +{UN['plain-r2']['pts']:.2f} for plain and +{UN['research-r2']['pts']:.2f} for research. The largest single "
      "contributor is the behavioural SMB fuzz-filename rule; SMB is one of the protocols the gate cannot test, so its only "
      "benign check is the hold-out's normal-traffic captures, on which it raised no alert.")
cur.figure("fig5-10_hunt_transfer.png", "Fig. 5-10 : Alerts of each hunt rule on each development capture, grouped by the capture it was written on", width=6.3)

cur.h2("Hold-out Evaluation")
ho_rows = [["Capture (22 Jan 2015)", "GT attack events (TCP/UDP)", "Detected by baseline v2", "Alerts"]]
cur.p("Every result above comes from the six development captures, on which rule families were selected and AI rules "
      "were written. Final claims need traffic that neither the team nor the model had looked at, so five captures from "
      "the other UNSW-NB15 day, 22 January 2015, were held out. That day's ground truth covers only 11:00–14:00 UTC; "
      "captures 1, 3 and 6 fall inside the window and measure detection, while captures 25 and 50 contain no labelled "
      "attacks and serve as unseen normal traffic, on which every alert is a false-positive candidate. Captures 1, 25 and "
      "50 were chosen for spread across the day before any label was examined; 3 and 6 were added, by time only, when it "
      "became clear that 25 and 50 fall outside the attack window. The rule for selecting what is tested — baseline v2 "
      "plus non-topology AI rules — was fixed before any hold-out replay, and every AI rule file was frozen (copied to "
      "rules/snapshots/) before the AI rules were replayed on the hold-out, once.")
cur.p(f"The frozen baseline v2 detects {pct(HO['base_det'], HO['tcpudp'])} of the {HO['tcpudp']:,} hold-out TCP/UDP "
      f"attack events, and {pct(HO['base_gt'], HO['base_alerts'])} of its alerts match an attack, against "
      f"{pct(BL['det'], BL['tcpudp'])} and {pct(BL['matching'], BL['alerts'])} on the development captures (Figure 5-11). "
      "The family selection therefore generalises to unseen traffic rather than reflecting tuning to the development day.")
HX = RND["holdout_extra"]
ho_tab = [["Condition", "Rules fired", "AI-rule alerts", "Matching an attack", "Attributable gain", "Genuine gain", "Alerts on benign captures"]]
for key, label in [("plain-r2-holdout", "Plain R2"), ("research-r2-holdout", "Research R2"), ("hunt-r1-holdout", "Hunt R1"), ("hunt2-r1-holdout", "Hunt2 R1")]:
    r_ = RND[key]
    cond = key.split("-")[0]
    bc = HX["benign_captures"][cond]
    ho_tab.append([label, f"{r_['rules_fired']} of {r_['rules_written']}", f"{r_['ai_alerts']:,}", pct(r_["ai_gt"], r_["ai_alerts"]),
                   f"+{r_['ai_new']} (+{pts(r_['ai_new'], r_['tcpudp'])})", f"+{r_['ai_new_genuine']} (+{pts(r_['ai_new_genuine'], r_['tcpudp'])})",
                   str(bc["25"] + bc["50"])])
cur.p(f"The frozen AI rules were then replayed on the hold-out (Table 5-5, Figure 5-12). The pattern of the development "
      f"set held. Plain round 2's large attributable gain was again almost entirely topology: genuine "
      f"+{pts(RND['plain-r2-holdout']['ai_new_genuine'], RND['plain-r2-holdout']['tcpudp'])} points. Research added "
      f"+{pts(RND['research-r2-holdout']['ai_new_genuine'], RND['research-r2-holdout']['tcpudp'])}. The hunt rules added "
      f"+{RND['hunt-r1-holdout']['ai_new_genuine']} events, +{pts(RND['hunt-r1-holdout']['ai_new_genuine'], RND['hunt-r1-holdout']['tcpudp'])} "
      f"points — slightly more than on the development set — with {pct(RND['hunt-r1-holdout']['ai_gt'], RND['hunt-r1-holdout']['ai_alerts'])} "
      "of their alerts on labelled attacks. No AI rule of any condition raised an alert on a host with no attacker involved, "
      f"or on either benign-only capture. Hunt2 added +{pts(RND['hunt2-r1-holdout']['ai_new_genuine'], RND['hunt2-r1-holdout']['tcpudp'])} "
      "points. Taking all four conditions together, the genuine events they add come to approximately "
      f"+{HX['combined']['genuine_new_union']} (+{HX['combined']['pts']:.1f} points), and the two hunt conditions together "
      f"+{HX['combined_by_set']['hunt+hunt2']['genuine_new_union']} (+{HX['combined_by_set']['hunt+hunt2']['pts']:.1f}); "
      "because each condition was attributed within its own replay, these unions are approximate.")
cur.table(t, ho_tab, 7, font=8, widths=[1.0, 0.8, 0.8, 0.9, 1.2, 1.1, 1.0])
cur.caption("Table 5-5: Frozen AI rules on the hold-out (captures 1, 3, 6: 4,634 TCP/UDP events; benign-only captures 25, 50)", "Table")
cur.figure("fig5-12_generalisation.png", "Fig. 5-12 : Genuine gain on all development captures, on development captures without rules, and on the hold-out", width=6.0)
h2 = RND["hunt2-r1"]
cur.h2("Adding a Keyword Reference (Hunt2)")
cur.p(f"Hunt2 added +{h2['ai_new_genuine']} genuine events on the development captures "
      f"(+{pts(h2['ai_new_genuine'], h2['tcpudp'])} points), +{UN['hunt2-r1']['pts']:.2f} points on captures 4, 5 and 14, "
      f"and +{pts(RND['hunt2-r1-holdout']['ai_new_genuine'], RND['hunt2-r1-holdout']['tcpudp'])} points on the hold-out, "
      f"with {pct(RND['hunt2-r1-holdout']['ai_gt'], RND['hunt2-r1-holdout']['ai_alerts'])} of its hold-out alerts on labelled "
      "attacks and none on benign traffic. That is consistent and generalises, but it is below the hunt condition and "
      "below the expectation recorded before the run (+1.2 to +2.0 points). The keyword tool did what it was built to do — "
      "no rule failed to load — yet it did not raise detection.")
cur.p("Figure 5-13 shows why. The two conditions found largely different attack events: of the hunt's 180 and hunt2's "
      "136 genuine development events, 82 are common, 98 were found only by the hunt (its SMB fuzz-filename rule alone "
      "contributes 59) and 54 only by hunt2 (its WebDAV PROPFIND rule for Windows DLLs, 36). Which attack families a run "
      "chooses to hunt decides its result, and that choice varies more between runs of the same procedure than the "
      "keyword tool changes it. With one run per capture per condition, the difference between hunt and hunt2 is within "
      "run-to-run variation; the union of the two conditions' rules is larger than either.")
cur.figure("fig5-14_hunt_overlap.png", "Fig. 5-13 : Genuine development events found by the hunt and hunt2 conditions, and each condition's top rules", width=6.3)

DT = _J("detectable.json")
cur.h2("What a Signature IDS Could Have Detected")
cur.p("Every percentage so far is measured against all labelled TCP/UDP attack events. Two narrower denominators test "
      "whether that is unfair to a signature IDS. Content-detectable events are those in which the attacker sent "
      "application data in a matching flow — more TCP bytes than headers alone account for, or any UDP datagram — so a "
      "content rule could in principle see them; events without data, such as SYN probes, can only be caught by rate or "
      "topology logic. (The TCP PSH flag could not be used: the traffic generator often sends data without it.) "
      "Ever-detected events are those caught by at least one configuration run in this project: the baseline, the "
      "all-rules-enabled control or a genuine AI rule. It is a practical, and circular, ceiling.")
dev_, ho_ = DT["dev"], DT["holdout"]
rows = [["Measure", "Development (6 captures)", "Hold-out (1, 3, 6)"],
        ["TCP/UDP attack events", f"{dev_['tcpudp']:,}", f"{ho_['tcpudp']:,}"],
        ["Content-detectable", f"{dev_['content']:,} ({pct(dev_['content'], dev_['tcpudp'])})", f"{ho_['content']:,} ({pct(ho_['content'], ho_['tcpudp'])})"],
        ["Ever-detected", f"{dev_['ever']:,} ({pct(dev_['ever'], dev_['tcpudp'])})", f"{ho_['ever']:,} ({pct(ho_['ever'], ho_['tcpudp'])})"],
        ["Baseline v2: all / content / ever",
         f"{pct(dev_['base']['all'], dev_['tcpudp'])} / {pct(dev_['base']['content'], dev_['content'])} / {pct(dev_['base']['ever'], dev_['ever'])}",
         f"{pct(ho_['base']['all'], ho_['tcpudp'])} / {pct(ho_['base']['content'], ho_['content'])} / {pct(ho_['base']['ever'], ho_['ever'])}"]]
for c, lab in (("plain", "Plain"), ("research", "Research"), ("hunt", "Hunt"), ("hunt2", "Hunt2")):
    gd, gh = dev_["gains"][c], ho_["gains"][c]
    rows.append([f"{lab} genuine gain, pts: all / content / ever",
                 f"+{pts(gd['all'], dev_['tcpudp'])} / +{pts(gd['content'], dev_['content'])} / +{pts(gd['all'], dev_['ever'])}",
                 f"+{pts(gh['all'], ho_['tcpudp'])} / +{pts(gh['content'], ho_['content'])} / +{pts(gh['all'], ho_['ever'])}"])
cur.table(rt, rows, 3, font=8, widths=[2.2, 1.5, 1.5])
cur.caption("Table 5-6: Detection against all, content-detectable and ever-detected attack events", "Table")
cur.p(f"Excluding events without data barely changes the picture: about three-quarters of attack events carried data, "
      f"and the baseline still detects only {pct(dev_['base']['content'], dev_['content'])} of those on the development "
      "captures. The gap is missing signatures, not traffic that no signature could see (Figure 5-14). Against the "
      f"ever-detected ceiling the human baseline already reaches {pct(dev_['base']['ever'], dev_['ever'])} (development) and "
      f"{pct(ho_['base']['ever'], ho_['ever'])} (hold-out), and the hunt rules add "
      f"+{pts(dev_['gains']['hunt']['all'], dev_['ever'])} and +{pts(ho_['gains']['hunt']['all'], ho_['ever'])} points of "
      "it — a more substantial share of what the project could catch than of what the dataset contains.")
cur.figure("fig5-13_detectability.png", "Fig. 5-14 : Baseline v2 detection against all, content-detectable and ever-detected attack events", width=6.3)

cur.h2("Why the Agent Did Not Write a Rule")
cur.p("Each hunt report ends with activity the model judged attack-like but left without a rule. Grouped by cause "
      "(Figure 5-15), these show where the remaining limits lie. A tooling gap — not knowing which keywords this Suricata "
      "version supports — led to guessed keywords and raw-byte fall-backs; the keyword tool closed it. A rule-language "
      "limit: high-entropy DNS names suggesting tunnelling or generated domains need a statistic over the name, which a "
      "plain signature cannot compute; Suricata's lua keyword could, but the agent cannot write Lua scripts. Our own design "
      "choices: randomised POP3, IMAP and SMTP sessions can only be separated from legitimate users by rate or source, but "
      "the procedure forbids pivoting on addresses and the gate cannot test those protocols, so the model, reasonably, did "
      "not guess. DCE/RPC bind fuzzing with random interface versions would need a raw byte test on the bind header, which "
      "the model avoided rather than write a broad port rule. Finally, some omissions were correct judgement: SNMP "
      "community probing was already covered by deployed rules, and lab-specific or over-narrow candidates were dropped.")
cur.figure("fig5-15_agent_limits.png", "Fig. 5-15 : Attack-like activity the hunt reports left without a rule, grouped by cause", width=6.0)
cur.figure("fig5-11_holdout_baseline.png", "Fig. 5-11 : Frozen baseline v2 on the development captures and on the hold-out captures", width=5.6)

thr = para("Sample size and provenance.")
cur = Cursor(thr)
cur.p([("Replay variance and attribution. ", True), ("Suricata replays of the same capture are not identical, so any "
      "comparison across replays mixes rule effects with timing effects. Round results are therefore attributed within a "
      "single replay; the earlier replay-versus-stored figures are superseded.", False)])
cur.p([("Rule classification. ", True), ("The topology, behavioural, signature and dataset-indicator classes were "
      "assigned from each rule's text, not from its alerts; a different reader might classify a borderline rule "
      "differently. The class of every rule is published with its reason (docs/results/round_rule_classes.json).", False)])
cur.p([("Hunt condition design. ", True), ("The hunt condition differs from the triage conditions in two ways at once — its "
      "procedure and the absence of the attacker range from its prompt — so the effect of each cannot be separated. Its "
      "known-good test relies on the testbed description and cannot test protocols that only external hosts use.", False)])
cur.p([("Reasoning carried across turns. ", True), ("Until the provider fix described in Section IV, the DeepSeek adapter "
      "discarded the model's reasoning whenever it answered in thinking mode, so the reasoning was neither logged nor "
      "returned on the next turn. Every earlier DeepSeek run — CIC-IDS2017, the first UNSW-NB15 runs, Experiment 1, the "
      "plain and research rounds and hunt capture 3 — ran with this defect; most of those runs also wrote visible text, "
      "which was carried, so they were affected less, but by how much cannot be measured after the fact. The hunt "
      "condition's gain coincides with the fix: its capture-3 rules (before) added 6 events, its capture-1 and capture-10 "
      "rules (after) 175. The comparison between the hunt and triage conditions is therefore confounded with the fix; "
      "re-running the plain and research conditions with reasoning carried would separate the two.", False)])
cur.p([("One run per capture. ", True), ("Each condition was run once per capture. The hunt and hunt2 conditions, which "
      "differ only by one tool, found largely different attacks (Figure 5-13), so run-to-run variation is of the same size "
      "as the differences between the hunt-style conditions; those differences should not be read as rankings.", False)])
cur.p([("Detectability proxy. ", True), ("Content-detectable is estimated from flow byte counts; very small payloads may be "
      "counted as header-only, and the ever-detected ceiling is defined by this project's own rule sets.", False)])

# ---- Section VI and VII additions
p = para("Several findings")
cur = Cursor(p)
cur.p([("Strong baselines change the question. ", True), (f"Tuning the human-written rules — re-enabling disabled families by "
      f"service — raised UNSW-NB15 detection from {pct(layer('ET Open'), TOT)} to {pct(layer('all extra + re-enabled'), TOT)}, "
      "more than any AI condition added. Against that baseline the triage-driven conditions' genuine contribution was a "
      "fraction of a point, and most of their apparent gain came from topology rules that only work because of how the "
      "dataset was built. Measuring only what the AI rules alone detected, and classifying every rule, was necessary to "
      "see this.", False)])
cur.p([("Replicating practice helps — once the agent keeps its own reasoning. ", True), ("Encoding the "
      "detection-engineering lifecycle and an engine-enforced test gate eliminated topology rules. With the model's "
      "reasoning carried across turns, the same procedure produced technique-level rules that added "
      f"+{pts(RND['hunt-r1']['ai_new_genuine'], RND['hunt-r1']['tcpudp'])} points on the development captures and "
      f"+{pts(RND['hunt-r1-holdout']['ai_new_genuine'], RND['hunt-r1-holdout']['tcpudp'])} on the hold-out, with no alert on "
      "benign traffic; rules keyed to single exploit instances did not transfer.", False)])
cur.p([("Knowledge of the rule language is not the bottleneck. ", True), ("A keyword reference removed every rule-loading "
      "failure but did not raise detection; what a run detects depends on which attack families it chooses to hunt, which "
      "varies between runs. Most missed attacks carried data, so the remaining gap is signatures nobody has written, and "
      "the limits the agent reported are mostly in the rule language and in our own safety choices.", False)])
fw = para("Environment-aware validation.")
cur = Cursor(fw)
cur.p([("Technique-level hunting. ", True), ("A variant of the hunt profile that requires rules on the technique — "
      "over-long parameters instead of exploit filler, failure rates for scans and brute force — and that tests each rule "
      "on a second capture before it is saved.", False)])
cur.p([("Separate the workflow from the fix. ", True), ("Re-run the plain and research conditions with the model's "
      "reasoning carried across turns, so that the hunt workflow's own contribution can be measured.", False)])
cur.p([("Several runs per capture. ", True), ("Because runs of the same procedure find different attacks, repeat each "
      "condition and keep the union of genuine rules, measuring both the spread and the combined gain.", False)])
cur.p([("Statistical and rate rules. ", True), ("Allow Suricata Lua rules for properties such as DNS label entropy, and "
      "extend the test gate to rate rules — for example, a threshold that must never trip for any internal client.", False)])

# ---- References (alphabetical insertion, red)
REFS2 = {
    "Anthropic 2025": ["Atkinson, J 2020, 'Capability abstraction', SpecterOps blog, 6 February, viewed 4 October 2026, https://specterops.io/blog/2020/02/06/capability-abstraction/"],
    "Denning, DE 1987": ["di Filippo, L, Bardhi, E, Agiollo, A, Palma, A, Bonomi, S & Kuipers, F 2026, 'Beyond the syntax: do security experts trust LLMs for NIDS rule engineering?', arXiv preprint arXiv:2607.05916.",
                         "Dragos 2023, 'Improving long tail analysis using Neighborhood Keeper', Dragos blog, 27 April, viewed 4 October 2026, https://www.dragos.com/blog/using-neighborhood-keeper-for-long-tail-analysis/"],
    "Ferrag, MA": ["Fraunhofer FKIE 2026, 'UNSW-NB15', COMIDDS: Comprehensive Open Malware Intrusion Detection Dataset Store, viewed 4 October 2026, https://fkie-cad.github.io/COMIDDS/content/datasets/unsw_nb15/"],
    "Lanvin, M": ["Li, J, Chai, Y, Du, L, Duan, C, Yan, H & Gu, Z 2025, 'GRIDAI: generating and repairing intrusion detection rules via collaboration among multiple LLM-based agents', arXiv preprint arXiv:2510.13257."],
    "Liao, HJ": ["Mitra, S, Neupane, S, Duclos, M, Mittal, S, Piplai, A, Rahman, MR, Zieglar, E & Rahimi, S 2025, 'FALCON: autonomous cyber threat intelligence mining with LLMs for IDS rule generation', arXiv preprint arXiv:2508.18684."],
    "OISF 2026": ["Palantir 2017, Alerting and detection strategy framework, GitHub repository, Palantir Technologies, viewed 4 October 2026, https://github.com/palantir/alerting-detection-strategy-framework"],
    "Proofpoint 2026": ["Rehman, MU, Piplai, A & Kantarcioglu, M 2026, 'RuleAutoPilot: synthesizing deployable Suricata rules from network traffic', arXiv preprint arXiv:2609.16231."],
}
for after, refs in REFS2.items():
    cur = Cursor(para(after))
    for ref in refs:
        cur.p(ref, template=T_REF)


# ---- v1 re-scored by attribution; counts the October material changed
V1 = _J("unsw_v1_attribution.json")
append(para("Detection on UNSW-NB15."),
       f" Re-scored by attribution within a single replay (Section V, Attribution and the Topology Trap), the AI rules "
       f"account for +{pts(V1['ai_new'], V1['tcpudp'])} points of events no other rule caught, "
       f"+{pts(V1['ai_new_genuine'], V1['tcpudp'])} of them from signature and behavioural rules: against stock ET Open "
       f"the gain is genuine, unlike the later rounds against the strengthened baseline.")
append(para("Every rule the models authored was traced to its session"),
       f" The audit covers the CIC-IDS2017 and first UNSW-NB15 rules; the {sum(_classes('plain').values()) + sum(_classes('research').values()) + sum(_classes('hunt').values())} "
       "rules written in the Experiment 3 rounds are classified in Attribution and the Topology Trap.")
append(para("The models wrote 32 rule definitions on CIC-IDS2017 and 18 on UNSW-NB15."),
       f" A further {sum(_classes('plain').values()) + sum(_classes('research').values()) + sum(_classes('hunt').values())} "
       "rules were written in the Experiment 3 rounds on the strengthened baseline.")

# ---- Lists of figures and tables (after Contents)
caption_styles()


def renumber_captions():
    """Number figures and tables per chapter in document order, and rewrite every reference to match."""
    import re as _r
    pat = _r.compile(r"\b(Fig\.|Figure|Figures|Table|Tables)(\s?)(\d+|[A-Z])-(\d+)\b")
    mapping = {"fig": {}, "tab": {}}
    counters = {}
    for p_ in d.paragraphs:
        if p_.style.name not in ("Figure Caption", "Table Caption"):
            continue
        m = _r.match(r"\s*(Fig\.|Table)\s?(\d+|[A-Z])-(\d+)", p_.text)
        if not m or not m.group(2).isdigit() or m.group(2) == "0":
            continue
        kind = "fig" if m.group(1) == "Fig." else "tab"
        ch = m.group(2)
        counters[(kind, ch)] = counters.get((kind, ch), 0) + 1
        mapping[kind][f"{ch}-{m.group(3)}"] = f"{ch}-{counters[(kind, ch)]}"
    changed = {k: {o: n for o, n in v.items() if o != n} for k, v in mapping.items()}

    def fix(text):
        def sub(m):
            kind = "fig" if m.group(1).startswith("Fig") else "tab"
            key = f"{m.group(3)}-{m.group(4)}"
            return f"{m.group(1)}{m.group(2)}{changed[kind].get(key, key)}"
        return pat.sub(sub, text)

    runs = [r_ for p_ in d.paragraphs for r_ in p_.runs]
    runs += [r_ for t_ in d.tables for row_ in t_.rows for c_ in row_.cells for p_ in c_.paragraphs for r_ in p_.runs]
    for r_ in runs:
        if pat.search(r_.text):
            new = fix(r_.text)
            if new != r_.text:
                r_.text = new
    return changed


RENUMBERED = renumber_captions()
figs = [p.text.strip() for p in d.paragraphs if p.style.name == "Figure Caption"]
tabs = [p.text.strip() for p in d.paragraphs if p.style.name == "Table Caption"]
abbr_heading = para("List of Abbreviations")
cur = Cursor(abbr_heading._p.getprevious())
list_field(cur, "List of Figures", "Figure Caption", figs)
list_field(cur, "List of Tables", "Table Caption", tabs)
update_fields_on_open()

d.save(DST)
print(f"Saved {DST.name}: {len(figs)} figure captions, {len(tabs)} table captions; renumbered {RENUMBERED}")
