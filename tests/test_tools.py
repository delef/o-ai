from langchain.messages import ToolMessage

from chefbot.tools import recipe_search, substitution_finder, unit_converter


def invoke(tool, call_id: str, **args):
    return tool.invoke(
        {
            "name": tool.name,
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }
    )


def test_recipe_tool_returns_content_and_artifact() -> None:
    message = invoke(recipe_search, "recipe-1", query="курки та картоплі")
    assert isinstance(message, ToolMessage)
    assert message.name == "recipe_search"
    assert message.artifact["kind"] == "recipe_search"
    assert message.artifact["status"] == "ok"
    assert message.artifact["matches"][0]["recipe"]["id"] == "chicken-potatoes"


def test_conversion_tool_exposes_structured_result() -> None:
    message = invoke(
        unit_converter,
        "conversion-1",
        amount=2,
        from_unit="склянки",
        to_unit="грами",
        product="борошно",
    )
    assert message.artifact["kind"] == "unit_converter"
    assert message.artifact["status"] == "ok"
    assert message.artifact["result"] == 300


def test_substitution_tool_reports_missing_data_without_invention() -> None:
    message = invoke(substitution_finder, "substitution-1", ingredient="трюфельна паста")
    assert message.artifact == {
        "kind": "substitution_finder",
        "status": "not_found",
        "ingredient": "трюфельна паста",
        "options": [],
    }
    assert "не знайдено" in message.content
