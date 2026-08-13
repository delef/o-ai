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


def test_recipe_editor_returns_a_complete_revision_with_reason() -> None:
    message = invoke(
        recipe_editor,
        "edit-1",
        reason="Ви попросили замінити курятину на індичку.",
        ingredients=[
            {"name": "філе індички", "quantity": 500, "unit": "г"},
            {"name": "картопля", "quantity": 700, "unit": "г"},
        ],
        steps=["Наріжте індичку та картоплю.", "Запікайте 45 хвилин."],
    )

    assert message.artifact == {
        "kind": "recipe_editor",
        "status": "ok",
        "reason": "Ви попросили замінити курятину на індичку.",
        "ingredients": [
            {"name": "філе індички", "quantity": 500, "unit": "г", "note": None},
            {"name": "картопля", "quantity": 700, "unit": "г", "note": None},
        ],
        "steps": ["Наріжте індичку та картоплю.", "Запікайте 45 хвилин."],
    }


def test_recipe_editor_rejects_an_update_without_a_reason() -> None:
    message = invoke(
        recipe_editor,
        "edit-2",
        reason="",
        ingredients=[{"name": "цибуля", "quantity": 1, "unit": "шт."}],
        steps=["Наріжте цибулю."],
    )

    assert message.artifact["status"] == "invalid"
    assert "причину" in message.content


def test_recipe_editor_keeps_a_missing_amount_for_canonicalization() -> None:
    message = invoke(
        recipe_editor,
        "edit-ingredient-only",
        reason="Ви попросили додати цибулю.",
        ingredients=[{"name": "цибуля"}],
        steps=["Наріжте цибулю."],
    )

    assert message.artifact == {
        "kind": "recipe_editor",
        "status": "ok",
        "reason": "Ви попросили додати цибулю.",
        "ingredients": [
            {"name": "цибуля", "quantity": None, "unit": None, "note": None}
        ],
        "steps": ["Наріжте цибулю."],
    }


def test_recipe_editor_schema_constrains_and_explains_step_updates() -> None:
    schema = recipe_editor.args_schema.model_json_schema()

    assert schema["required"] == ["reason", "ingredients", "steps"]
    assert "action" not in schema["properties"]
    assert "повний актуальний список" in schema["properties"]["ingredients"]["description"].casefold()
    assert "усі кроки" in schema["properties"]["steps"]["description"].casefold()


def test_recipe_editor_returns_a_complete_revised_recipe() -> None:
    message = invoke(
        recipe_editor,
        "revision-1",
        reason="Ви попросили додати цибулю.",
        ingredients=[
            {"name": "куряче філе", "quantity": 500, "unit": "г", "note": None},
            {"name": "цибуля", "quantity": 1, "unit": "шт.", "note": None},
        ],
        steps=[
            "Наріжте курку та цибулю.",
            "Запікайте 45 хвилин.",
        ],
    )

    assert message.artifact == {
        "kind": "recipe_editor",
        "status": "ok",
        "reason": "Ви попросили додати цибулю.",
        "ingredients": [
            {"name": "куряче філе", "quantity": 500, "unit": "г", "note": None},
            {"name": "цибуля", "quantity": 1, "unit": "шт.", "note": None},
        ],
        "steps": [
            "Наріжте курку та цибулю.",
            "Запікайте 45 хвилин.",
        ],
    }
