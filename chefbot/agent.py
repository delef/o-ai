from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import AIMessage, ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from chefbot.prompt import SYSTEM_PROMPT
from chefbot.tools import get_tools


DEFAULT_MODEL = "gpt-4o-mini"


class MissingAPIKeyError(RuntimeError):
    """Raised when a live ChefBot agent is requested without a key."""


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )


@dataclass(frozen=True)
class ToolEvent:
    name: str
    status: str
    content: str
    artifact: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChefBotResult:
    messages: list[BaseMessage]
    answer: str
    tool_events: list[ToolEvent]
    usage: TokenUsage
    latency_ms: int


@wrap_tool_call
def safe_tool_errors(request: ToolCallRequest, handler):
    try:
        return handler(request)
    except Exception:
        return ToolMessage(
            content="Інструмент тимчасово не виконав запит. Спробуйте ще раз або уточніть дані.",
            tool_call_id=request.tool_call["id"],
            name=request.tool_call["name"],
            artifact={
                "kind": request.tool_call["name"],
                "status": "error",
            },
        )


def create_chefbot(
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 700,
):
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "OPENAI_API_KEY не налаштовано. Додайте ключ у Colab Secrets або змінні середовища."
        )

    model = ChatOpenAI(
        api_key=key,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=30,
        max_retries=2,
        stream_usage=True,
    )
    return create_agent(
        model=model,
        tools=get_tools(),
        system_prompt=SYSTEM_PROMPT,
        middleware=[safe_tool_errors],
    )


def _message_text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        return "\n".join(
            block.get("text", "")
            for block in message.content
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}
        ).strip()
    return str(message.content)


def _usage_from_message(message: BaseMessage) -> TokenUsage:
    metadata = getattr(message, "usage_metadata", None) or {}
    details = metadata.get("input_token_details") or {}
    return TokenUsage(
        input_tokens=int(metadata.get("input_tokens", 0)),
        output_tokens=int(metadata.get("output_tokens", 0)),
        total_tokens=int(metadata.get("total_tokens", 0)),
        cached_input_tokens=int(details.get("cache_read", 0)),
    )


def _events(messages: Iterable[BaseMessage]) -> list[ToolEvent]:
    events = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        artifact = message.artifact if isinstance(message.artifact, dict) else {}
        events.append(
            ToolEvent(
                name=message.name or str(artifact.get("kind", "unknown")),
                status=str(artifact.get("status", "unknown")),
                content=_message_text(message),
                artifact=artifact,
            )
        )
    return events


def run_chefbot(agent, messages: list[BaseMessage | dict[str, Any]]) -> ChefBotResult:
    started = time.perf_counter()
    state = agent.invoke({"messages": messages})
    all_messages = list(state["messages"])
    generated = all_messages[len(messages):]
    answer = next(
        (_message_text(message) for message in reversed(generated) if isinstance(message, AIMessage) and _message_text(message)),
        "",
    )
    usage = TokenUsage()
    for message in generated:
        if isinstance(message, AIMessage):
            usage = usage + _usage_from_message(message)

    return ChefBotResult(
        messages=all_messages,
        answer=answer,
        tool_events=_events(generated),
        usage=usage,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )
