"""Model provider adapters — Anthropic and OpenAI-compatible (DeepSeek)."""

import json
import os
from dataclasses import dataclass
from typing import Any

from .tools import TOOL_DEFINITIONS


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ModelResponse:
    text: str
    tool_calls: list
    stop_reason: str
    input_tokens: int
    output_tokens: int
    raw: Any


def _to_openai_tools(anthropic_tools):
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in anthropic_tools
    ]


class AnthropicProvider:
    max_tool_result_chars = 15000

    def __init__(self, model, system_prompt, tools=None):
        import anthropic
        self.tools = tools or TOOL_DEFINITIONS
        self._mod = anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.system = system_prompt
        self.last_response = None

    def create_messages(self, user_text):
        return [{"role": "user", "content": user_text}]

    def append_user(self, messages, text):
        messages.append({"role": "user", "content": text})

    def call(self, messages):
        with self.client.messages.stream(
            model=self.model,
            max_tokens=16000,
            system=self.system,
            tools=self.tools,
            thinking={"type": "adaptive"},
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "thinking":
                        yield {"type": "thinking_start"}
                    elif event.content_block.type == "text":
                        yield {"type": "text_start"}
                elif event.type == "content_block_delta":
                    if event.delta.type == "thinking_delta":
                        yield {"type": "thinking", "text": event.delta.thinking}
                    elif event.delta.type == "text_delta":
                        yield {"type": "text", "text": event.delta.text}

            response = stream.get_final_message()

        text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        stop_map = {"end_turn": "end", "tool_use": "tool_use", "pause_turn": "pause"}
        self.last_response = ModelResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_map.get(response.stop_reason, response.stop_reason),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw=response.content,
        )

    def append_assistant(self, messages, response):
        messages.append({"role": "assistant", "content": response.raw})

    def append_tool_results(self, messages, results):
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tc_id, "content": content}
                for tc_id, content in results
            ],
        })

    def compact(self, messages):
        if len(messages) <= 4:
            return messages
        compacted = [messages[0]]
        for msg in messages[1:]:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                trimmed = []
                for item in msg["content"]:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        content = item.get("content", "")
                        if isinstance(content, str) and len(content) > 500:
                            item = {**item, "content": content[:500] + "\n[compacted]"}
                    trimmed.append(item)
                compacted.append({**msg, "content": trimmed})
            elif msg["role"] == "assistant":
                if hasattr(msg.get("content"), "__iter__") and not isinstance(
                    msg["content"], str
                ):
                    trimmed = [
                        b
                        for b in msg["content"]
                        if not (hasattr(b, "type") and b.type == "thinking")
                    ]
                    compacted.append({**msg, "content": trimmed})
                else:
                    compacted.append(msg)
            else:
                compacted.append(msg)
        return compacted

    def is_context_error(self, exc):
        return isinstance(exc, self._mod.BadRequestError) and (
            "request_too_large" in str(exc) or "413" in str(exc)
        )


class OpenAIProvider:
    max_tool_result_chars = 8000

    def __init__(self, model, system_prompt, tools=None):
        import openai
        self.tools = tools or TOOL_DEFINITIONS
        self._mod = openai
        self.model = model
        self.system_prompt = system_prompt
        self.last_response = None

        if model.startswith("deepseek"):
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "DEEPSEEK_API_KEY environment variable is not set. "
                    "Get your key at https://platform.deepseek.com/"
                )
            self.client = openai.OpenAI(
                base_url="https://api.deepseek.com",
                api_key=api_key,
            )
        else:
            raise ValueError(f"Unsupported OpenAI-compatible model: {model}")

    def create_messages(self, user_text):
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_text},
        ]

    def append_user(self, messages, text):
        messages.append({"role": "user", "content": text})

    def call(self, messages):
        tools = _to_openai_tools(self.tools)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            max_tokens=8192,
            stream=True,
            stream_options={"include_usage": True},
        )

        text_parts = []
        reasoning_parts = []
        tool_calls_acc = {}
        finish_reason = None
        usage_input = 0
        usage_output = 0
        text_started = False
        thinking_started = False

        for chunk in stream:
            if chunk.usage:
                usage_input = chunk.usage.prompt_tokens or 0
                usage_output = chunk.usage.completion_tokens or 0

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            delta = choice.delta
            if not delta:
                continue

            # DeepSeek thinking mode streams its reasoning in reasoning_content, not content. It must be shown,
            # logged and passed back with the assistant turn, or the model loses its own plan every turn.
            reasoning = (delta.model_extra or {}).get("reasoning_content")
            if reasoning:
                if not thinking_started:
                    yield {"type": "thinking_start"}
                    thinking_started = True
                yield {"type": "thinking", "text": reasoning}
                reasoning_parts.append(reasoning)

            if delta.content:
                if not text_started:
                    yield {"type": "text_start"}
                    text_started = True
                yield {"type": "text", "text": delta.content}
                text_parts.append(delta.content)

            if delta.tool_calls:
                text_started = False
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += (
                                tc_delta.function.arguments
                            )

        parsed_calls = []
        for idx in sorted(tool_calls_acc.keys()):
            tc = tool_calls_acc[idx]
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            parsed_calls.append(
                ToolCall(id=tc["id"], name=tc["name"], input=args)
            )

        stop_map = {"stop": "end", "tool_calls": "tool_use", "length": "max_tokens"}
        full_text = "".join(text_parts)
        full_reasoning = "".join(reasoning_parts)

        self.last_response = ModelResponse(
            text=full_text,
            tool_calls=parsed_calls,
            stop_reason=stop_map.get(finish_reason, finish_reason or "end"),
            input_tokens=usage_input,
            output_tokens=usage_output,
            raw={
                "content": full_text or None,
                "reasoning_content": full_reasoning or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.input),
                        },
                    }
                    for tc in parsed_calls
                ]
                if parsed_calls
                else None,
            },
        )

    def append_assistant(self, messages, response):
        msg = {"role": "assistant", "content": response.raw["content"] or ""}
        if response.raw.get("reasoning_content"):
            msg["reasoning_content"] = response.raw["reasoning_content"]
        if response.raw["tool_calls"]:
            msg["tool_calls"] = response.raw["tool_calls"]
        messages.append(msg)

    def append_tool_results(self, messages, results):
        for tc_id, content in results:
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": content,
            })

    def compact(self, messages):
        if len(messages) <= 4:
            return messages
        compacted = [messages[0], messages[1]]
        for msg in messages[2:]:
            if msg["role"] == "tool":
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 500:
                    msg = {**msg, "content": content[:500] + "\n[compacted]"}
            elif msg["role"] == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 1000:
                    msg = {**msg, "content": content[:1000] + "\n[compacted]"}
            compacted.append(msg)
        return compacted

    def is_context_error(self, exc):
        err_str = str(exc).lower()
        return isinstance(exc, self._mod.BadRequestError) and (
            "context_length" in err_str
            or "maximum context" in err_str
            or "too many tokens" in err_str
        )


def get_provider(model, system_prompt, tools=None):
    if model.startswith("deepseek"):
        return OpenAIProvider(model, system_prompt, tools)
    return AnthropicProvider(model, system_prompt, tools)
