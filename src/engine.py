import anthropic
import json
import sys
from typing import Generator
from .tools import TOOL_DEFINITIONS, execute_tool
from .prompts import SYSTEM_PROMPT

MAX_TURNS = 30
MAX_TOOL_RESULT_CHARS = 15000


def _compact_messages(messages: list) -> list:
    """Trim tool results in older turns to keep context within API limits."""
    if len(messages) <= 4:
        return messages

    compacted = [messages[0]]  # keep original user prompt
    for msg in messages[1:]:
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            trimmed_content = []
            for item in msg["content"]:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    content = item.get("content", "")
                    if isinstance(content, str) and len(content) > 500:
                        item = {**item, "content": content[:500] + "\n[compacted]"}
                trimmed_content.append(item)
            compacted.append({**msg, "content": trimmed_content})
        elif msg["role"] == "assistant":
            if hasattr(msg.get("content"), '__iter__') and not isinstance(msg["content"], str):
                trimmed = []
                for block in msg["content"]:
                    if hasattr(block, 'type') and block.type == "thinking":
                        continue  # drop thinking blocks to save space
                    trimmed.append(block)
                compacted.append({**msg, "content": trimmed})
            else:
                compacted.append(msg)
        else:
            compacted.append(msg)
    return compacted


def _emit(event_type: str, data: dict) -> dict:
    return {"type": event_type, **data}


def run_triage(eve_path: str, model: str = "claude-opus-5",
               approve_suppress: callable = None) -> Generator[dict, None, None]:
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

    approve_suppress: callback that takes (sid, reason, line) and returns True/False.
                     If None, all suppress proposals require manual approval (returned as events).
    """
    client = anthropic.Anthropic()

    user_message = f"Triage the alerts in {eve_path}. Follow the triage procedure step by step."

    messages = [{"role": "user", "content": user_message}]
    total_input_tokens = 0
    total_output_tokens = 0

    for turn in range(MAX_TURNS):
        try:
            with client.messages.stream(
                model=model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                thinking={"type": "adaptive"},
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "thinking":
                            yield _emit("thinking_start", {})
                        elif event.content_block.type == "text":
                            yield _emit("text_start", {})
                    elif event.type == "content_block_delta":
                        if event.delta.type == "thinking_delta":
                            yield _emit("thinking", {"text": event.delta.thinking})
                        elif event.delta.type == "text_delta":
                            yield _emit("text", {"text": event.delta.text})

                response = stream.get_final_message()

        except anthropic.BadRequestError as e:
            if "request_too_large" in str(e) or "413" in str(e):
                yield _emit("text", {"text": "\n[Context too large — compacting conversation history...]\n"})
                messages = _compact_messages(messages)
                continue
            yield _emit("error", {"message": f"API error: {e}"})
            return
        except anthropic.APIError as e:
            yield _emit("error", {"message": f"API error: {e}"})
            return

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        yield _emit("usage", {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "turn": turn + 1
        })

        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
            yield _emit("done", {"report": final_text})
            return

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
            yield _emit("done", {"report": final_text})
            return

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool in tool_use_blocks:
            yield _emit("tool_call", {
                "name": tool.name,
                "input": tool.input,
                "tool_use_id": tool.id
            })

            if tool.name in ("write_file", "append_to_file"):
                content = tool.input.get("content", "")
                file_path = tool.input.get("file_path", "")
                if "threshold.config" in file_path and "suppress" in content.lower():
                    yield _emit("suppress_proposal", {
                        "file_path": file_path,
                        "content": content,
                        "tool_use_id": tool.id
                    })
                    if approve_suppress:
                        approved = approve_suppress(file_path, content)
                    else:
                        approved = False

                    if not approved:
                        result = "BLOCKED: Suppress rule proposals require human approval. The proposal has been shown to the engineer."
                    else:
                        result = execute_tool(tool.name, tool.input)
                else:
                    result = execute_tool(tool.name, tool.input)
            else:
                result = execute_tool(tool.name, tool.input)

            yield _emit("tool_result", {
                "name": tool.name,
                "output": result[:3000],
                "tool_use_id": tool.id
            })

            if len(result) > MAX_TOOL_RESULT_CHARS:
                result = result[:MAX_TOOL_RESULT_CHARS] + f"\n\n[OUTPUT CAPPED at {MAX_TOOL_RESULT_CHARS} chars. Use more specific filters or aggregation.]"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool.id,
                "content": result
            })

        messages.append({"role": "user", "content": tool_results})

    yield _emit("error", {"message": f"Reached maximum turns ({MAX_TURNS}) without completing triage."})
