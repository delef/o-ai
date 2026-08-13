from langchain.messages import AIMessage, HumanMessage, ToolMessage

from chefbot.agent import MissingAPIKeyError, create_chefbot, run_chefbot


class FakeAgent:
    def invoke(self, state):
        prior = list(state["messages"])
        return {
            "messages": [
                *prior,
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recipe_search",
                            "args": {"query": "борщ"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                    usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
                ),
                ToolMessage(
                    content="Борщ",
                    tool_call_id="call-1",
                    name="recipe_search",
                    artifact={"kind": "recipe_search", "status": "ok", "matches": []},
                ),
                AIMessage(
                    content="Ось рецепт борщу.",
                    usage_metadata={"input_tokens": 120, "output_tokens": 20, "total_tokens": 140},
                ),
            ]
        }


def test_missing_key_fails_before_model_creation(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        create_chefbot(api_key=None)
    except MissingAPIKeyError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected MissingAPIKeyError")


def test_run_extracts_answer_tool_artifact_and_usage() -> None:
    result = run_chefbot(FakeAgent(), [HumanMessage(content="Дай рецепт борщу")])
    assert result.answer == "Ось рецепт борщу."
    assert result.tool_events[0].name == "recipe_search"
    assert result.tool_events[0].artifact["status"] == "ok"
    assert result.usage.input_tokens == 220
    assert result.usage.output_tokens == 30
    assert result.usage.total_tokens == 250
    assert result.latency_ms >= 0


def test_run_does_not_count_usage_from_prior_history() -> None:
    prior = AIMessage(
        content="Стара відповідь",
        usage_metadata={"input_tokens": 999, "output_tokens": 999, "total_tokens": 1998},
    )
    result = run_chefbot(FakeAgent(), [HumanMessage(content="Продовжуй"), prior])
    assert result.usage.total_tokens == 250
