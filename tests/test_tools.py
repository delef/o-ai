from langchain.messages import ToolMessage

from chefbot.tools import recipe_editor, recipe_search, substitution_finder, unit_converter


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


def test_recipe_editor_returns_a_structured_replace_patch_with_reason() -> None:
    message = invoke(
        recipe_editor,
        "edit-1",
        action="replace",
        ingredient="куряче філе",
        replacement="філе індички",
        reason="Ви попросили замінити курятину на індичку.",
        step_number=1,
        step_text="Наріжте індичку, картоплю та моркву.",
    )

    assert message.artifact == {
        "kind": "recipe_editor",
        "status": "ok",
        "action": "replace",
        "ingredient": "куряче філе",
        "replacement": "філе індички",
        "quantity": None,
        "unit": None,
        "note": None,
        "step_number": 1,
        "step_text": "Наріжте індичку, картоплю та моркву.",
        "reason": "Ви попросили замінити курятину на індичку.",
    }


def test_recipe_editor_rejects_an_update_without_a_reason() -> None:
    message = invoke(
        recipe_editor,
        "edit-2",
        action="add",
        ingredient="цибуля",
        reason="",
    )

    assert message.artifact["status"] == "invalid"
    assert "причину" in message.content
