"""Agentic triage loop — single loop, provider-agnostic."""

import re
from typing import Generator
from .tools import execute_tool, tool_definitions
from .prompts import build_system_prompt
from .profiles import PROFILES, task_message
from .providers import get_provider

MAX_TURNS = 100


def _emit(event_type: str, data: dict) -> dict:
    return {"type": event_type, **data}


def _alert_lines(text: str) -> list:
    return [l.strip() for l in text.splitlines() if re.match(r"\s*alert\b", l)]


def _gate_write(ds: dict, name: str, tool_input: dict, passed: dict):
    """For profiles with require_test: only appends of rules that passed test_rule unchanged, to the profile's rule file."""
    if not ds.get("require_test"):
        return None
    path = str(tool_input.get("file_path", "")).lstrip("./")
    if path != ds["rule_file"]:
        return f"BLOCKED: in this profile you may only write to {ds['rule_file']}."
    if name == "write_file":
        return "BLOCKED: use append_to_file — the rule file already holds rules from earlier rounds."
    untested = [l for l in _alert_lines(tool_input.get("content", "")) if l not in passed.values()]
    if untested:
        return ("BLOCKED: these rules have not passed test_rule in exactly this form (run test_rule on them first):\n"
                + "\n".join(u[:160] for u in untested))
    return None


def run_triage(eve_path: str, model: str = "claude-opus-5",
               approve_suppress: callable = None, profile: str = "cic", dataset: str = None) -> Generator[dict, None, None]:
    """Run the AI triage loop on an eve.json file.

    Yields event dicts that the UI can render:
      {"type": "thinking", "text": "..."}
      {"type": "text", "text": "..."}
      {"type": "tool_call", "name": "...", "input": {...}}
      {"type": "tool_result", "name": "...", "output": "..."}
      {"type": "suppress_proposal", "sid": ..., "reason": "...", "line": "..."}
      {"type": "done", "report": "..."}
      {"type": "error", "message": "..."}
      {"type": "usage", "input_tokens": ..., "output_tokens": ...}

    approve_suppress: callback that takes (file_path, content) and returns True/False.
                     If None, all suppress proposals require manual approval.
    """
    profile = dataset or profile  # 'dataset' is the old name of the profile argument
    if profile not in PROFILES:
        yield _emit("error", {"message": f"Unknown profile '{profile}'."})
        return
    try:
        provider = get_provider(model, build_system_prompt(profile),
                                tool_definitions(PROFILES[profile].get("extra_tools", ())))
    except ValueError as e:
        yield _emit("error", {"message": str(e)})
        return

    ds = PROFILES[profile]
    suricata_config = ds["suricata_config"]
    alerts_only = ds.get("alerts_only", False)
    extra_blocked = ds.get("extra_blocked", ())
    logs_allow = ds.get("logs_allow")
    passed_rules = {}  # sid -> rule text that passed test_rule (require_test profiles)
    user_message = task_message(profile, eve_path)
    messages = provider.create_messages(user_message)
    total_input_tokens = 0
    total_output_tokens = 0

    max_turns = ds.get("max_turns", MAX_TURNS)
    for turn in range(max_turns):
        try:
            for event in provider.call(messages):
                yield event
            response = provider.last_response
        except Exception as e:
            if provider.is_context_error(e):
                yield _emit("text", {
                    "text": "\n[Context too large — compacting conversation history...]\n"
                })
                messages = provider.compact(messages)
                continue
            yield _emit("error", {"message": f"API error: {e}"})
            return

        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens
        yield _emit("usage", {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "turn": turn + 1,
        })

        if response.stop_reason == "end":
            yield _emit("done", {"report": response.text})
            return

        if response.stop_reason == "max_tokens":
            # A reply cut off by the output limit is not a finished triage; discard it and ask for a shorter one.
            yield _emit("text", {"text": "\n[Reply exceeded the output limit and was discarded; asking the model to continue more concisely.]\n"})
            provider.append_user(messages, "Your previous reply was cut off by the output length limit and was discarded. "
                                           "Continue the triage from where you were, keeping each reply shorter.")
            continue

        if response.stop_reason == "pause":
            provider.append_assistant(messages, response)
            continue

        if not response.tool_calls:
            yield _emit("done", {"report": response.text})
            return

        provider.append_assistant(messages, response)

        tool_results = []
        for tc in response.tool_calls:
            yield _emit("tool_call", {
                "name": tc.name,
                "input": tc.input,
                "tool_use_id": tc.id,
            })

            blocked = _gate_write(ds, tc.name, tc.input, passed_rules) if tc.name in ("write_file", "append_to_file") else None
            if blocked:
                result = blocked
            elif tc.name in ("write_file", "append_to_file"):
                content = tc.input.get("content", "")
                file_path = tc.input.get("file_path", "")
                if "threshold.config" in file_path and "suppress" in content.lower():
                    yield _emit("suppress_proposal", {
                        "file_path": file_path,
                        "content": content,
                        "tool_use_id": tc.id,
                    })
                    if approve_suppress:
                        approved = approve_suppress(file_path, content)
                    else:
                        approved = False

                    if not approved:
                        result = (
                            "BLOCKED: Suppress rule proposals require human approval. "
                            "The proposal has been shown to the engineer."
                        )
                    else:
                        result = execute_tool(tc.name, tc.input, suricata_config, alerts_only, extra_blocked, logs_allow)
                else:
                    result = execute_tool(tc.name, tc.input, suricata_config, alerts_only, extra_blocked, logs_allow)
            else:
                result = execute_tool(tc.name, tc.input, suricata_config, alerts_only, extra_blocked, logs_allow)

            if tc.name == "test_rule":
                for sid in re.findall(r"VERDICT sid:(\d+) PASS", result):
                    for line in _alert_lines(tc.input.get("rule_text", "")):
                        if re.search(rf"\bsid\s*:\s*{sid}\s*;", line):
                            passed_rules[int(sid)] = line

            yield _emit("tool_result", {
                "name": tc.name,
                "output": result[:3000],
                "tool_use_id": tc.id,
            })

            if len(result) > provider.max_tool_result_chars:
                result = (
                    result[:provider.max_tool_result_chars]
                    + f"\n\n[OUTPUT CAPPED at {provider.max_tool_result_chars} chars. "
                    "Use more specific filters or aggregation.]"
                )

            tool_results.append((tc.id, result))

        provider.append_tool_results(messages, tool_results)

    yield _emit("error", {
        "message": f"Reached maximum turns ({max_turns}) without completing triage."
    })
