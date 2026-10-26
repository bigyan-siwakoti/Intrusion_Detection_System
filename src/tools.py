import json
import re
import subprocess
import os
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_RESULT_LINES = 150

# The model may only see what a sensor analyst would have. Ground-truth labels, project notes,
# earlier transcripts and results would leak the answer, so everything else is off-limits.
READABLE_DIRS = [PROJECT_ROOT / d for d in ("logs", "config", "rules", "data/pcaps", "data/slices")]
UNREADABLE_DIRS = [PROJECT_ROOT / d for d in ("data/labels", "rules/snapshots")]


def _under(path: Path, base: Path) -> bool:
    base = base.resolve()
    return path == base or base in path.parents


def _is_blocked(path: Path, extra_blocked=(), logs_allow=None) -> bool:
    path = path.resolve()
    if any(_under(path, d) for d in UNREADABLE_DIRS):
        return True
    if logs_allow:
        # Profile that may read only some run folders (e.g. not the logs other conditions' rules produced).
        logs = (PROJECT_ROOT / "logs").resolve()
        if logs in path.parents and not re.fullmatch(logs_allow, path.relative_to(logs).parts[0]):
            return True
    if any(path == (PROJECT_ROOT / e).resolve() for e in extra_blocked):
        return True
    if any(_under(path, d) for d in READABLE_DIRS):
        return False
    # Directories that lead to a readable dir (project root, data/) may be listed.
    return not any(d.resolve() == path or path in d.resolve().parents for d in READABLE_DIRS)


WRITABLE_PATHS = [
    PROJECT_ROOT / "config" / "threshold.config",
    PROJECT_ROOT / "rules" / "generated",
]


def _is_writable(path: Path) -> bool:
    path = path.resolve()
    for allowed in WRITABLE_PATHS:
        allowed = allowed.resolve()
        if path == allowed or allowed in path.parents:
            return True
    return False


def query_eve_json(eve_path: str, jq_filter: str) -> str:
    """Run a jq query against an eve.json file. Returns results capped at MAX_RESULT_LINES."""
    full_path = (PROJECT_ROOT / eve_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if _is_blocked(full_path):
        return "Error: access to this path is not permitted."
    if not full_path.exists():
        return f"Error: {eve_path} not found."

    try:
        result = subprocess.run(
            ["jq", "-c", jq_filter, str(full_path)],
            capture_output=True, text=True, timeout=60, shell=False
        )
    except subprocess.TimeoutExpired:
        return "Error: query timed out after 60 seconds. Try a more specific filter or add aggregation."

    if result.returncode != 0:
        err_lines = result.stderr.strip().split("\n")
        if len(err_lines) > 10:
            return f"jq error (showing 10 of {len(err_lines)} error lines):\n" + "\n".join(err_lines[:10]) + "\n\nHint: eve.json is NDJSON (one JSON object per line). Do NOT use group_by, unique, min_by, max_by — those require slurping. Use select() for filtering, and count_by for any aggregation/counting."
        return f"jq error: {result.stderr.strip()}"

    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    total = len(lines)
    if total > MAX_RESULT_LINES:
        truncated = lines[:MAX_RESULT_LINES]
        return "\n".join(truncated) + f"\n\n[TRUNCATED: showing {MAX_RESULT_LINES} of {total} results. Use count_by for aggregation, or add select() filters to narrow the query.]"
    return result.stdout.strip() if lines else "(no results)"


def _count_jq_output(full_path: Path, jq_filter: str, timeout: int = 120) -> str:
    """Run jq streaming, count unique output lines with Python Counter. No shell."""
    try:
        result = subprocess.run(
            ["jq", "-c", "-r", jq_filter, str(full_path)],
            capture_output=True, text=True, timeout=timeout, shell=False
        )
    except subprocess.TimeoutExpired:
        return "Error: query timed out. Try a more specific filter."

    if result.returncode != 0:
        err = result.stderr.strip()
        if "group_by" in err or "unique" in err or "min_by" in err or "max_by" in err:
            return f"jq error: {err}\n\nHint: eve.json is NDJSON (one object per line). group_by/unique/min_by/max_by require slurping and will fail. Just use select() and output the field you want — this tool counts for you."
        return f"jq error: {err}"

    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    if not lines or lines == [""]:
        return "(no results)"

    counts = Counter(lines)
    ranked = counts.most_common()
    out = [f"{count:>7}  {value}" for value, count in ranked]
    return "\n".join(out)


def count_alerts(eve_path: str) -> str:
    """Count alerts grouped by signature. Returns signature name, SID, and count sorted by frequency."""
    full_path = (PROJECT_ROOT / eve_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if _is_blocked(full_path):
        return "Error: access to this path is not permitted."
    if not full_path.exists():
        return f"Error: {eve_path} not found."

    jq_filter = r'select(.event_type=="alert") | "\(.alert.signature) [sid:\(.alert.signature_id)]"'
    return _count_jq_output(full_path, jq_filter)


def count_by(eve_path: str, jq_filter: str) -> str:
    """Count unique values from a jq filter on eve.json. Use this for any aggregation:
    counting event types, IP pairs, protocol replies, ports, etc."""
    full_path = (PROJECT_ROOT / eve_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if _is_blocked(full_path):
        return "Error: access to this path is not permitted."
    if not full_path.exists():
        return f"Error: {eve_path} not found."

    return _count_jq_output(full_path, jq_filter)


def read_file(file_path: str) -> str:
    """Read a file from the project directory."""
    full_path = (PROJECT_ROOT / file_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if _is_blocked(full_path):
        return "Error: access to this path is not permitted."
    if not full_path.exists():
        return f"Error: {file_path} not found."

    try:
        content = full_path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"

    lines = content.split("\n")
    if len(lines) > MAX_RESULT_LINES:
        return "\n".join(lines[:MAX_RESULT_LINES]) + f"\n\n[TRUNCATED: showing {MAX_RESULT_LINES} of {len(lines)} lines.]"
    return content


def write_file(file_path: str, content: str) -> str:
    """Write content to a file. Only config/threshold.config and rules/generated/* are writable."""
    full_path = (PROJECT_ROOT / file_path).resolve()
    if not _is_writable(full_path):
        return f"Error: writing to {file_path} is not allowed. Writable paths: config/threshold.config, rules/generated/*"

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Successfully wrote {len(content)} bytes to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


def append_to_file(file_path: str, content: str) -> str:
    """Append content to a file. Only config/threshold.config and rules/generated/* are writable."""
    full_path = (PROJECT_ROOT / file_path).resolve()
    if not _is_writable(full_path):
        return f"Error: writing to {file_path} is not allowed. Writable paths: config/threshold.config, rules/generated/*"

    try:
        with open(full_path, "a") as f:
            f.write(content)
        return f"Successfully appended {len(content)} bytes to {file_path}"
    except Exception as e:
        return f"Error appending to file: {e}"


def run_suricata(pcap_path: str, run_name: str, config: str = "config/suricata.yaml") -> str:
    """Run Suricata on a pcap file. Returns the log output."""
    pcap_full = (PROJECT_ROOT / pcap_path).resolve()
    if not str(pcap_full).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: pcap path must be inside the project directory."
    if not pcap_full.exists():
        return f"Error: {pcap_path} not found."

    safe_name = "".join(c for c in run_name if c.isalnum() or c in "-_")
    if not safe_name:
        return "Error: run_name must contain alphanumeric characters, hyphens, or underscores."

    log_dir = PROJECT_ROOT / "logs" / safe_name
    log_dir.mkdir(parents=True, exist_ok=True)

    config_path = PROJECT_ROOT / config
    try:
        result = subprocess.run(
            ["suricata", "-r", str(pcap_full),
             "-l", str(log_dir),
             "-c", str(config_path)],
            capture_output=True, text=True, timeout=600, shell=False
        )
    except subprocess.TimeoutExpired:
        return f"Error: Suricata timed out after 10 minutes. Log dir: logs/{safe_name}/"

    output = f"Exit code: {result.returncode}\nLog directory: logs/{safe_name}/\n"
    if result.stdout:
        output += f"\nstdout:\n{result.stdout[-2000:]}"
    if result.stderr:
        output += f"\nstderr:\n{result.stderr[-2000:]}"

    suricata_log = log_dir / "suricata.log"
    if suricata_log.exists():
        log_content = suricata_log.read_text()
        log_lines = log_content.strip().split("\n")
        output += f"\n\nsuricata.log (last 30 lines):\n" + "\n".join(log_lines[-30:])

    return output


def list_directory(dir_path: str) -> str:
    """List files in a project directory."""
    full_path = (PROJECT_ROOT / dir_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if _is_blocked(full_path):
        return "Error: access to this path is not permitted."
    if not full_path.exists():
        return f"Error: {dir_path} not found."
    if not full_path.is_dir():
        return f"Error: {dir_path} is not a directory."

    entries = []
    for item in sorted(full_path.iterdir()):
        if _is_blocked(item):
            continue
        if item.is_dir():
            entries.append(f"  {item.name}/")
        else:
            size = item.stat().st_size
            if size > 1_000_000:
                entries.append(f"  {item.name}  ({size / 1_000_000:.1f} MB)")
            elif size > 1_000:
                entries.append(f"  {item.name}  ({size / 1_000:.1f} KB)")
            else:
                entries.append(f"  {item.name}  ({size} B)")
    return "\n".join(entries) if entries else "(empty directory)"



_RULE_CACHE = {}
DATASET_TERMS = re.compile(r"unsw|nb-?15|nb15|cic-?ids|ids-?2017|cicflowmeter|kaggle|ixia|perfectstorm|breaking ?point|strike ?center|strikecenter", re.I)
KB_PATH = PROJECT_ROOT / "data" / "kb" / "nvd.sqlite"
REF_ALLOW = ("nvd.nist.gov", "cve.mitre.org", "cwe.mitre.org", "microsoft.com", "cisco.com", "oracle.com", "apache.org",
             "redhat.com", "debian.org", "ubuntu.com", "suse.com", "securityfocus.com", "kb.cert.org", "us-cert.gov",
             "cisa.gov", "openssl.org", "php.net", "mozilla.org", "adobe.com", "ibm.com", "hp.com", "sun.com", "vmware.com")


def _loaded_rules(config: str) -> list:
    """(sid, msg, file, text) for every enabled rule loaded by the given Suricata config."""
    if config in _RULE_CACHE:
        return _RULE_CACHE[config]
    cfg = (PROJECT_ROOT / config).read_text()
    base = re.search(r"^default-rule-path:\s*(\S+)", cfg, re.M).group(1)
    block = re.search(r"^rule-files:\n((?:\s+- .*\n)+)", cfg, re.M).group(1)
    rules = []
    for rel in re.findall(r"-\s*(\S+)", block):
        path = Path(base) / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not re.match(r"\s*alert\b", line):
                continue
            sid = re.search(r"\bsid\s*:\s*(\d+)", line)
            msg = re.search(r'msg\s*:\s*"([^"]*)"', line)
            if sid:
                rules.append((int(sid.group(1)), msg.group(1) if msg else "", rel, line))
    _RULE_CACHE[config] = rules
    return rules


def search_rules(term: str, config: str) -> str:
    """Search the rules currently loaded into Suricata (message, references, content) for a term."""
    term = term.strip()
    if len(term) < 3:
        return "Error: search term must be at least 3 characters."
    rules = _loaded_rules(config)
    t = term.lower()
    hits = [r for r in rules if t in r[1].lower()] or [r for r in rules if t in r[3].lower()]
    if not hits:
        return f"No loaded rule matches '{term}' ({len(rules)} rules searched). No signature for this is currently deployed."
    out = [f"{len(hits)} loaded rule(s) match '{term}' ({len(rules)} searched); showing up to 25:"]
    out += [f"  sid:{sid}  [{f}]  {msg}" for sid, msg, f, _ in hits[:25]]
    return "\n".join(out)


def lookup_vulnerability(query: str) -> str:
    """Look up vulnerability background in a local copy of the NVD CVE database (2002-2016)."""
    import sqlite3
    q = query.strip()
    if DATASET_TERMS.search(q):
        return "Error: queries about evaluation datasets or traffic generators are not permitted. Ask about the vulnerability, product or technique instead."
    if not KB_PATH.exists():
        return "Error: vulnerability knowledge base not built (python -m src.kb.build_nvd)."
    con = sqlite3.connect(f"file:{KB_PATH}?mode=ro", uri=True)
    cve = re.fullmatch(r"(?i)cve-\d{4}-\d{4,7}", q)
    if cve:
        rows = con.execute("SELECT id, published, cvss, cwe, description, refs FROM cve WHERE id = ?", (q.upper(),)).fetchall()
    else:
        words = [w for w in re.findall(r"[A-Za-z0-9_.]+", q) if len(w) > 1]
        if not words:
            return "Error: empty query."
        fts = " ".join('"' + w.replace('"', "") + '"' for w in words)
        rows = con.execute("SELECT c.id, c.published, c.cvss, c.cwe, c.description, c.refs FROM cve_fts f JOIN cve c ON c.rowid = f.rowid "
                           "WHERE cve_fts MATCH ? ORDER BY bm25(cve_fts) LIMIT 8", (fts,)).fetchall()
    con.close()
    if not rows:
        return f"No NVD record matches '{q}'."
    out = []
    for cid, pub, score, cwe, desc, refs in rows:
        allowed = [u for u in json.loads(refs) if any(dom in u for dom in REF_ALLOW)][:3]
        out.append(f"{cid} (published {pub}, CVSS {score or 'n/a'}, {cwe or 'no CWE'})\n  {desc[:600]}"
                   + ("\n  refs: " + " | ".join(allowed) if allowed else ""))
    return f"NVD results for '{q}':\n" + "\n".join(out)


def stack_values(eve_path: str, jq_filter: str, order: str = "rare", limit: int = 60) -> str:
    """Stack counting: values of a jq expression with their counts, rarest (or commonest) first."""
    full_path = (PROJECT_ROOT / eve_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if _is_blocked(full_path):
        return "Error: access to this path is not permitted."
    if not full_path.exists():
        return f"Error: {eve_path} not found."
    try:
        result = subprocess.run(["jq", "-c", "-r", jq_filter, str(full_path)],
                                capture_output=True, text=True, timeout=120, shell=False)
    except subprocess.TimeoutExpired:
        return "Error: query timed out. Try a more specific filter."
    if result.returncode != 0:
        return f"jq error: {result.stderr.strip()}"
    counts = Counter(l for l in result.stdout.split("\n") if l)
    if not counts:
        return "(no results)"
    limit = max(1, min(int(limit), 200))
    ranked = counts.most_common()
    if order == "rare":
        ranked = sorted(ranked, key=lambda kv: (kv[1], kv[0]))
    head = f"{len(counts)} distinct values, {sum(counts.values())} total; showing {min(limit, len(ranked))} {order}st first"
    return head + "\n" + "\n".join(f"{c:>7}  {v[:300]}" for v, c in ranked[:limit])


_KEYWORDS = None


def suricata_keywords(query: str) -> str:
    """Keywords this Suricata build supports, filtered by name or description; full detail for an exact name."""
    global _KEYWORDS
    q = query.strip().lower()
    if not q:
        return "Error: give a keyword name or a word to search for, e.g. 'smb', 'file.name', 'cert'."
    if _KEYWORDS is None:
        out = subprocess.run(["suricata", "--list-keywords=csv"], capture_output=True, text=True, timeout=60).stdout
        _KEYWORDS = []
        for line in out.splitlines()[1:]:
            parts = line.split(";")
            if len(parts) >= 2 and parts[0]:
                _KEYWORDS.append((parts[0], parts[1], ";".join(parts[2:]).strip(";")))
    exact = [k for k in _KEYWORDS if k[0].lower() == q]
    if exact:
        detail = subprocess.run(["suricata", f"--list-keywords={exact[0][0]}"], capture_output=True, text=True, timeout=60).stdout.strip()
        return detail or f"{exact[0][0]}: {exact[0][1]}"
    hits = [k for k in _KEYWORDS if q in k[0].lower() or q in k[1].lower()]
    if not hits:
        return f"No keyword in this Suricata build (8.0.6) matches '{query}'. It does not exist here."
    shown = hits[:40]
    return (f"{len(hits)} keyword(s) in this Suricata build match '{query}'" + (f"; showing 40" if len(hits) > 40 else "") + ":\n"
            + "\n".join(f"  {n} — {d}" for n, d, _ in shown))


RULE_HEADER = re.compile(r"^(\s*alert\s+\S+\s+)(\S+)\s+(\S+)\s+(->|<>)\s+(\S+)\s+(\S+)(\s*\()")


def _home_nets(config: str) -> list:
    import ipaddress
    m = re.search(r'^\s*HOME_NET:\s*"\[?([^"\]]*)\]?"', (PROJECT_ROOT / config).read_text(), re.M)
    return [ipaddress.ip_network(c.strip()) for c in m.group(1).split(",") if c.strip()] if m else []


def _role_counts(eve: Path, nets: list) -> dict:
    """Alerts per sid by direction role: ext->int, int->ext, int->int, ext->ext."""
    import ipaddress
    inside = lambda ip: any(ipaddress.ip_address(ip) in n for n in nets)
    out = {}
    if not eve.exists():
        return out
    with open(eve) as fh:
        for line in fh:
            ev = json.loads(line)
            if ev.get("event_type") != "alert":
                continue
            role = ("int" if inside(ev["src_ip"]) else "ext") + "->" + ("int" if inside(ev["dest_ip"]) else "ext")
            c = out.setdefault(ev["alert"]["signature_id"], Counter())
            c[role] += 1
    return out


def _fmt_roles(c: Counter) -> str:
    return (f"{sum(c.values())} alerts (external->internal {c['ext->int']}, internal->external {c['int->ext']}, "
            f"internal->internal {c['int->int']}, external->external {c['ext->ext']})")


def test_rule(rule_text: str, pcap_path: str, config: str) -> str:
    """Syntax-check candidate rules, replay a capture with only them, then again with addresses widened to any."""
    import shutil
    import uuid
    work = PROJECT_ROOT / "logs" / "_test_rule" / uuid.uuid4().hex[:10]
    try:
        return _test_rule(rule_text, pcap_path, config, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)  # each replay writes a full eve.json (~60 MB)


def _test_rule(rule_text: str, pcap_path: str, config: str, work: Path) -> str:
    rules = [l.strip() for l in rule_text.splitlines() if re.match(r"\s*alert\b", l)]
    if not rules:
        return "Error: no 'alert' rule found in rule_text."
    sids = [re.search(r"\bsid\s*:\s*(\d+)", r) for r in rules]
    if not all(sids):
        return "Error: every rule needs a sid."
    sids = [int(s.group(1)) for s in sids]
    pcap = (PROJECT_ROOT / pcap_path).resolve()
    if not _under(pcap, PROJECT_ROOT / "data/pcaps") or not pcap.is_file():
        return "Error: pcap_path must be a capture under data/pcaps/."
    widened = []
    for r in rules:
        m = RULE_HEADER.match(r)
        if not m:
            return f"Error: could not parse the rule header (action proto src sport -> dst dport): {r[:120]}"
        widened.append(RULE_HEADER.sub(lambda m: f"{m.group(1)}any any {m.group(4)} any any{m.group(7)}", r, count=1))

    for sub in ("syntax", "written", "widened"):
        (work / sub).mkdir(parents=True)
    (work / "written.rules").write_text("\n".join(rules) + "\n")
    (work / "widened.rules").write_text("\n".join(widened) + "\n")
    cfg = str(PROJECT_ROOT / config)

    chk = subprocess.run(["suricata", "-T", "-c", cfg, "-S", str(work / "written.rules"), "-l", str(work / "syntax")],
                         capture_output=True, text=True, timeout=120)
    if chk.returncode != 0:
        log = (work / "syntax" / "suricata.log")
        text = (log.read_text() if log.exists() else "") + chk.stderr + chk.stdout
        errs = [l for l in text.splitlines() if "rror" in l][:8]
        return "Syntax: FAILED\n" + "\n".join(errs) + "\nVERDICT: FAIL (rule does not load)"

    procs = [subprocess.Popen(["suricata", "-c", cfg, "-S", str(work / f"{v}.rules"), "--set", "threshold-file=",
                               "-k", "none", "-r", str(pcap), "-l", str(work / v)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for v in ("written", "widened")]
    try:
        for p in procs:
            p.wait(timeout=600)
    except subprocess.TimeoutExpired:
        for p in procs:
            p.kill()
        return "Error: replay timed out after 10 minutes."

    nets = _home_nets(config)
    written = _role_counts(work / "written" / "eve.json", nets)
    wide = _role_counts(work / "widened" / "eve.json", nets)
    out = [f"Syntax: OK ({len(rules)} rule(s))", f"Capture: {pcap_path}"]
    for sid in sids:
        w, x = written.get(sid, Counter()), wide.get(sid, Counter())
        out.append(f"sid:{sid}\n  as written:               {_fmt_roles(w)}\n  widened to any -> any:    {_fmt_roles(x)}")
        if not w:
            out.append(f"VERDICT sid:{sid} FAIL — raises no alerts on this capture (flowbits set by other rules are not loaded here).")
        elif x["int->int"]:
            out.append(f"VERDICT sid:{sid} FAIL — without its address constraint the rule matches {x['int->int']} times between "
                       "internal hosts (known-good). Its precision comes from the source address, not from the behaviour.")
        else:
            out.append(f"VERDICT sid:{sid} PASS")
    return "\n".join(out)


TOOL_DEFINITIONS = [
    {
        "name": "query_eve_json",
        "description": "Run a jq query against an eve.json file. Results are capped at 150 lines — if truncated, use aggregation (group_by, unique, length) or filters to narrow. Path is relative to the project root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "eve_path": {
                    "type": "string",
                    "description": "Path to eve.json relative to project root, e.g. 'logs/tuesday-threshold-v2/eve.json'"
                },
                "jq_filter": {
                    "type": "string",
                    "description": "A jq filter expression, e.g. 'select(.event_type==\"alert\") | .alert.signature'"
                }
            },
            "required": ["eve_path", "jq_filter"],
            "additionalProperties": False
        }
    },
    {
        "name": "count_alerts",
        "description": "Count alerts in an eve.json grouped by signature. Returns signature name, SID, and count sorted by frequency. Use this as a first step to understand what alerts are present.",
        "input_schema": {
            "type": "object",
            "properties": {
                "eve_path": {
                    "type": "string",
                    "description": "Path to eve.json relative to project root"
                }
            },
            "required": ["eve_path"],
            "additionalProperties": False
        }
    },
    {
        "name": "count_by",
        "description": "Count unique values produced by a jq filter on eve.json. The filter runs in streaming mode (one object per line) — use select() and output a string. This tool counts occurrences and sorts by frequency. Use for ANY aggregation: event types, IP pairs, FTP replies, ports, protocol fields. Examples: '.event_type' counts all event types; 'select(.event_type==\"ftp\") | .ftp.reply[0]' counts FTP reply codes; 'select(.event_type==\"alert\") | \"\\(.src_ip) -> \\(.dest_ip)\"' counts alert IP pairs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "eve_path": {
                    "type": "string",
                    "description": "Path to eve.json relative to project root"
                },
                "jq_filter": {
                    "type": "string",
                    "description": "A jq filter that produces one value per line. Use select() to filter, then output a string or field. Do NOT use group_by, unique, min_by, max_by — those require slurping."
                }
            },
            "required": ["eve_path", "jq_filter"],
            "additionalProperties": False
        }
    },
    {
        "name": "read_file",
        "description": "Read a file from the project directory. Path is relative to project root. Large files are truncated to 150 lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to project root, e.g. 'config/threshold.config'"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Only config/threshold.config and rules/generated/* are writable. Overwrites existing content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to project root"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                }
            },
            "required": ["file_path", "content"],
            "additionalProperties": False
        }
    },
    {
        "name": "append_to_file",
        "description": "Append content to a file. Only config/threshold.config and rules/generated/* are writable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to project root"
                },
                "content": {
                    "type": "string",
                    "description": "Content to append"
                }
            },
            "required": ["file_path", "content"],
            "additionalProperties": False
        }
    },
    {
        "name": "run_suricata",
        "description": "Run Suricata on a pcap file with the project config. Output goes to logs/<run_name>/. Timeout: 10 minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pcap_path": {
                    "type": "string",
                    "description": "Path to pcap file relative to project root"
                },
                "run_name": {
                    "type": "string",
                    "description": "Name for the log directory (alphanumeric, hyphens, underscores)"
                }
            },
            "required": ["pcap_path", "run_name"],
            "additionalProperties": False
        }
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories in a project directory with sizes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "Directory path relative to project root, e.g. 'logs/'"
                }
            },
            "required": ["dir_path"],
            "additionalProperties": False
        }
    },
]

RESEARCH_TOOL_DEFINITIONS = {
    "search_rules": {
        "name": "search_rules",
        "description": "Search the detection rules currently loaded into Suricata (rule message, references such as CVE ids, and content) for a term, e.g. a CVE id, product, protocol or technique. Use it before writing a rule, to check whether a signature is already deployed.",
        "input_schema": {"type": "object", "properties": {"term": {"type": "string", "description": "Search term, e.g. 'CVE-2008-4250', 'portmap', 'MS08-067', 'BGP'"}},
                         "required": ["term"], "additionalProperties": False},
    },
    "lookup_vulnerability": {
        "name": "lookup_vulnerability",
        "description": "Look up vulnerability background in a local copy of the NVD CVE database (2002-2016): affected product, flaw type (CWE), severity and description. Query by CVE id or by keywords describing the product and flaw. Use it when an attack is confirmed but search_rules finds no deployed signature, to understand the vulnerability before writing a rule. Queries about datasets or traffic generators are refused.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "CVE id (e.g. 'CVE-2008-4250') or keywords (e.g. 'Solaris rwalld format string')"}},
                         "required": ["query"], "additionalProperties": False},
    },
    "stack_values": {
        "name": "stack_values",
        "description": "Stack counting over eve.json: counts each value a jq expression produces and lists them rarest first "
                       "(order 'rare') or commonest first (order 'common'), with the number of distinct values and the total. "
                       "The jq filter runs per event (NDJSON): use select() and output one string per event, e.g. "
                       "'select(.event_type==\"http\") | .http.http_user_agent'.",
        "input_schema": {"type": "object", "properties": {
            "eve_path": {"type": "string", "description": "Path to eve.json relative to project root"},
            "jq_filter": {"type": "string", "description": "jq filter producing one value per event"},
            "order": {"type": "string", "enum": ["rare", "common"], "description": "rare (default) or common"},
            "limit": {"type": "integer", "description": "values to show, default 60, max 200"}},
            "required": ["eve_path", "jq_filter"], "additionalProperties": False},
    },
    "suricata_keywords": {
        "name": "suricata_keywords",
        "description": "Look up rule keywords supported by this Suricata build (8.0.6): give a keyword name for its exact "
                       "description and documentation link, or a word (e.g. 'smb', 'tls', 'dns', 'file') to list matching "
                       "keywords. Use it before writing a rule with a keyword you are not certain exists in this version.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Keyword name (e.g. 'file.name') or search word (e.g. 'smb')"}},
            "required": ["query"], "additionalProperties": False},
    },
    "test_rule": {
        "name": "test_rule",
        "description": "Validate candidate Suricata rules on a capture. Checks syntax, replays the capture with only these rules, "
                       "then replays again with each rule's addresses and ports widened to 'any any -> any any'. Reports alerts "
                       "per sid by direction (external/internal hosts) and a VERDICT per sid. FAIL if the rule raises no alerts, "
                       "or if the widened rule fires between internal hosts (known-good traffic). Takes about a minute.",
        "input_schema": {"type": "object", "properties": {
            "rule_text": {"type": "string", "description": "One or more rules, one per line (comment lines allowed)"},
            "pcap_path": {"type": "string", "description": "Capture to replay, e.g. 'data/pcaps/unsw/3.pcap'"}},
            "required": ["rule_text", "pcap_path"], "additionalProperties": False},
    },
}


TOOL_DISPATCH = {
    "query_eve_json": lambda inp: query_eve_json(inp["eve_path"], inp["jq_filter"]),
    "count_alerts": lambda inp: count_alerts(inp["eve_path"]),
    "count_by": lambda inp: count_by(inp["eve_path"], inp["jq_filter"]),
    "read_file": lambda inp: read_file(inp["file_path"]),
    "write_file": lambda inp: write_file(inp["file_path"], inp["content"]),
    "append_to_file": lambda inp: append_to_file(inp["file_path"], inp["content"]),
    "run_suricata": lambda inp: run_suricata(inp["pcap_path"], inp["run_name"], inp["_config"]),
    "list_directory": lambda inp: list_directory(inp["dir_path"]),
    "search_rules": lambda inp: search_rules(inp["term"], inp["_config"]),
    "lookup_vulnerability": lambda inp: lookup_vulnerability(inp["query"]),
    "stack_values": lambda inp: stack_values(inp["eve_path"], inp["jq_filter"], inp.get("order", "rare"), inp.get("limit", 60)),
    "test_rule": lambda inp: test_rule(inp["rule_text"], inp["pcap_path"], inp["_config"]),
    "suricata_keywords": lambda inp: suricata_keywords(inp["query"]),
}


def tool_definitions(extra=()):
    return TOOL_DEFINITIONS + [RESEARCH_TOOL_DEFINITIONS[n] for n in extra]


def execute_tool(name: str, tool_input: dict, suricata_config: str = "config/suricata.yaml",
                 alerts_only: bool = False, extra_blocked=(), logs_allow=None) -> str:
    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        return f"Error: unknown tool '{name}'"
    for k in ("file_path", "dir_path", "eve_path", "pcap_path"):
        if k in tool_input and _is_blocked(PROJECT_ROOT / str(tool_input[k]), extra_blocked, logs_allow):
            return "Error: access to this path is not permitted."
    tool_input = dict(tool_input)
    if alerts_only:
        # Bare-alert condition: the model sees alert events only, never flow/app-layer context.
        if name in ("query_eve_json", "count_by"):
            tool_input["jq_filter"] = f'select(.event_type=="alert") | ({tool_input["jq_filter"]})'
        if name == "read_file" and str(tool_input.get("file_path", "")).endswith((".json", "stats.log")):
            return "Error: this file cannot be read in this condition; only alert data is available."
    try:
        return handler({**tool_input, "_config": suricata_config})
    except Exception as e:
        return f"Error executing {name}: {e}"
