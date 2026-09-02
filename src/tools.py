import json
import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_RESULT_LINES = 150

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
            return f"jq error (showing 10 of {len(err_lines)} error lines):\n" + "\n".join(err_lines[:10]) + "\n\nHint: eve.json has one JSON object per line. Do NOT use 'unique' or 'group_by' directly — those require slurping. Use streaming filters: select(), pipe to sort/uniq via count_alerts, or use [., inputs] to slurp."
        return f"jq error: {result.stderr.strip()}"

    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    total = len(lines)
    if total > MAX_RESULT_LINES:
        truncated = lines[:MAX_RESULT_LINES]
        return "\n".join(truncated) + f"\n\n[TRUNCATED: showing {MAX_RESULT_LINES} of {total} results. Use aggregation (group_by, unique, length, etc.) or add filters to narrow the query.]"
    return result.stdout.strip() if lines else "(no results)"


def count_alerts(eve_path: str) -> str:
    """Count alerts grouped by signature. Returns signature name, SID, and count sorted by frequency."""
    full_path = (PROJECT_ROOT / eve_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
    if not full_path.exists():
        return f"Error: {eve_path} not found."

    # Streaming approach: jq -c (no -s) pipes through sort | uniq -c | sort -rn
    # This handles multi-GB eve.json files without loading everything into RAM.
    cmd = (
        f'jq -c \'select(.event_type=="alert") | '
        f'{{sig: .alert.signature, sid: .alert.signature_id}}\' '
        f'{str(full_path)} | sort | uniq -c | sort -rn'
    )
    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=120, shell=False
        )
    except subprocess.TimeoutExpired:
        return "Error: aggregation timed out. The eve.json file may be very large."

    if result.returncode != 0:
        return f"Error: {result.stderr.strip()}"

    return result.stdout.strip() if result.stdout.strip() else "(no alerts found)"


def read_file(file_path: str) -> str:
    """Read a file from the project directory."""
    full_path = (PROJECT_ROOT / file_path).resolve()
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        return "Error: path must be inside the project directory."
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


def run_suricata(pcap_path: str, run_name: str) -> str:
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

    config_path = PROJECT_ROOT / "config" / "suricata.yaml"
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
    if not full_path.exists():
        return f"Error: {dir_path} not found."
    if not full_path.is_dir():
        return f"Error: {dir_path} is not a directory."

    entries = []
    for item in sorted(full_path.iterdir()):
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

TOOL_DISPATCH = {
    "query_eve_json": lambda inp: query_eve_json(inp["eve_path"], inp["jq_filter"]),
    "count_alerts": lambda inp: count_alerts(inp["eve_path"]),
    "read_file": lambda inp: read_file(inp["file_path"]),
    "write_file": lambda inp: write_file(inp["file_path"], inp["content"]),
    "append_to_file": lambda inp: append_to_file(inp["file_path"], inp["content"]),
    "run_suricata": lambda inp: run_suricata(inp["pcap_path"], inp["run_name"]),
    "list_directory": lambda inp: list_directory(inp["dir_path"]),
}


def execute_tool(name: str, tool_input: dict) -> str:
    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        return f"Error: unknown tool '{name}'"
    try:
        return handler(tool_input)
    except Exception as e:
        return f"Error executing {name}: {e}"
