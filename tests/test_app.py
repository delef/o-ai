import re

from langchain.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

from app import PAGE_STYLE, apply_recipe_edits, get_api_key, latest_recipe
from chefbot.agent import ToolEvent


class FakeFollowUpAgent:
    def invoke(self, state):
        return {
            "messages": [
                *state["messages"],
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recipe_editor",
                            "args": {
                                "action": "replace",
                                "ingredient": "куряче філе",
                                "replacement": "філе індички",
                                "reason": "Ви попросили замінити курятину на індичку.",
                                "step_number": 1,
                                "step_text": "Наріжте індичку, картоплю та моркву.",
                            },
                            "id": "edit-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="Рецепт оновлено.",
                    tool_call_id="edit-1",
                    name="recipe_editor",
                    artifact={
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
                    },
                ),
                AIMessage(
                    content=(
                        "Ось повний рецепт: курка, картопля, морква, цибуля. "
                        "Наріжте все та запікайте."
                    )
                ),
            ]
        }


class TwoTurnFollowUpAgent:
    def invoke(self, state):
        user_turns = [
            message
            for message in state["messages"]
            if getattr(message, "type", "") == "human"
        ]
        if len(user_turns) == 1:
            return {
                "messages": [
                    *state["messages"],
                    AIMessage(content="Перша відповідь."),
                ]
            }
        return {
            "messages": [
                *state["messages"],
                AIMessage(content="Друга відповідь."),
            ]
        }


def test_get_api_key_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    assert get_api_key({"OPENAI_API_KEY": "secret-key"}) == "environment-key"


def test_get_api_key_falls_back_to_streamlit_secret(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_api_key({"OPENAI_API_KEY": "secret-key"}) == "secret-key"


def test_latest_recipe_uses_verified_recipe_tool_artifact() -> None:
    recipe = {"id": "chicken-potatoes", "name": "курка з картоплею"}
    events = [
        ToolEvent(
            name="recipe_search",
            status="ok",
            content="result",
            artifact={
                "kind": "recipe_search",
                "status": "ok",
                "matches": [{"recipe": recipe}],
            },
        )
    ]
    assert latest_recipe(events) == recipe


def test_initial_streamlit_screen_renders_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    assert not app.exception
    assert app.title[0].value == "Що є у вас сьогодні?"
    assert app.multiselect[0].value == ["куряче філе", "картопля", "морква"]


def test_ingredient_label_is_visible(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    assert app.multiselect[0].proto.label_visibility.value == 0


def test_empty_selection_disables_search_and_explains_requirement(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    app.multiselect[0].set_value([]).run()
    assert app.button[0].disabled
    assert app.caption[0].value == "Додайте хоча б один продукт."


def test_ingredient_selection_is_not_batched_inside_a_form(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    assert app.multiselect[0].proto.form_id == ""


def test_ingredient_picker_uses_one_session_state_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run(timeout=10)

    assert "ingredient-picker" not in app.session_state.filtered_state
    app.multiselect[0].set_value(["рис", "помідори"]).run(timeout=10)
    assert app.session_state["ingredients"] == ["рис", "помідори"]


def test_changing_ingredients_clears_stale_search_result(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run(timeout=10)
    app.session_state["current_recipe"] = {
        "id": "old",
        "name": "Старий результат",
        "time_minutes": 1,
        "servings": 1,
        "ingredients": [{"name": "рис", "quantity": 1, "unit": "г", "note": None}],
        "steps": ["Старий крок"],
    }
    app.session_state["last_answer"] = "Стара відповідь"
    app.session_state["messages"] = ["old"]

    app.multiselect[0].set_value(["рис"]).run(timeout=10)

    assert app.session_state["current_recipe"] is None
    assert app.session_state["last_answer"] == ""
    assert app.session_state["messages"] == []
    assert app.session_state["search_phase"] == "idle"


def test_searching_state_is_visible_and_disables_repeat_submit(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run(timeout=10)
    app.session_state["search_phase"] = "searching"
    app.run(timeout=10)

    assert app.button[0].label == "Шукаємо страву…"
    assert app.button[0].disabled
    assert app.status[0].label == "ChefBot шукає перевірений рецепт…"
    assert app.status[0].state == "running"
    assert any(
        "@keyframes chef-search-spin" in element.value
        and "animation: chef-search-spin" in element.value
        for element in app.markdown
    )


def test_idle_search_icon_does_not_receive_spinner_animation(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run(timeout=10)

    assert not any(
        "@keyframes chef-search-spin" in element.value for element in app.markdown
    )


def test_follow_up_is_hidden_until_conversation_context_exists(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    assert not app.chat_input


def test_recipe_edits_update_the_whole_recipe_and_describe_latest_changes() -> None:
    recipe = {
        "id": "chicken-potatoes",
        "name": "курка з картоплею",
        "time_minutes": 55,
        "servings": 4,
        "ingredients": [
            {"name": "куряче філе", "quantity": 500, "unit": "г", "note": None},
            {"name": "картопля", "quantity": 700, "unit": "г", "note": None},
        ],
        "steps": ["Наріжте курку та картоплю.", "Запікайте 45 хвилин."],
    }
    events = [
        ToolEvent(
            name="recipe_editor",
            status="ok",
            content="Рецепт оновлено.",
            artifact={
                "kind": "recipe_editor",
                "status": "ok",
                "action": "replace",
                "ingredient": "куряче філе",
                "replacement": "філе індички",
                "quantity": None,
                "unit": None,
                "note": None,
                "step_number": 1,
                "step_text": "Наріжте індичку та картоплю.",
                "reason": "Ви попросили замінити курятину на індичку.",
            },
        )
    ]

    updated, changes = apply_recipe_edits(recipe, events)

    assert updated["ingredients"][0] == {
        "name": "філе індички",
        "quantity": 500,
        "unit": "г",
        "note": None,
    }
    assert updated["steps"][0] == "Наріжте індичку та картоплю."
    assert changes == {
        "ingredients": [
            {
                "name": "філе індички",
                "reason": "Ви попросили замінити курятину на індичку.",
            }
        ],
        "steps": [
            {
                "index": 0,
                "reason": "Ви попросили замінити курятину на індичку.",
            }
        ],
        "removed_ingredients": [],
    }


def test_recipe_edit_can_add_an_ingredient_without_inventing_quantity() -> None:
    recipe = {
        "id": "chicken-potatoes",
        "name": "курка з картоплею",
        "time_minutes": 55,
        "servings": 4,
        "ingredients": [],
        "steps": ["Наріжте курку, картоплю та моркву."],
    }
    events = [
        ToolEvent(
            name="recipe_editor",
            status="ok",
            content="До рецепта додано «цибуля».",
            artifact={
                "kind": "recipe_editor",
                "status": "ok",
                "action": "add",
                "ingredient": "цибуля",
                "replacement": "",
                "quantity": None,
                "unit": None,
                "note": None,
                "step_number": 1,
                "step_text": "Наріжте курку, картоплю, моркву та цибулю.",
                "reason": "Ви попросили додати цибулю.",
            },
        )
    ]

    updated, changes = apply_recipe_edits(recipe, events)

    assert updated["ingredients"][-1] == {
        "name": "цибуля",
        "quantity": None,
        "unit": None,
        "note": None,
    }
    assert updated["steps"][0] == "Наріжте курку, картоплю, моркву та цибулю."
    assert changes["ingredients"] == [
        {"name": "цибуля", "reason": "Ви попросили додати цибулю."}
    ]
    assert changes["steps"] == [
        {"index": 0, "reason": "Ви попросили додати цибулю."}
    ]


def test_discussion_transcript_and_inline_recipe_change_are_visible(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run(timeout=10)
    app.session_state["current_recipe"] = {
        "id": "chicken-potatoes",
        "name": "курка з картоплею",
        "time_minutes": 55,
        "servings": 4,
        "ingredients": [
            {"name": "філе індички", "quantity": 500, "unit": "г", "note": None}
        ],
        "steps": ["Наріжте індичку, картоплю та моркву."],
    }
    app.session_state["chat_history"] = [
        {"role": "user", "content": "Чим замінити куряче філе?"},
        {"role": "assistant", "content": "Можна використати філе індички."},
    ]
    app.session_state["recipe_changes"] = {
        "ingredients": [
            {
                "name": "філе індички",
                "reason": "Ви попросили замінити курятину на індичку.",
            }
        ],
        "steps": [],
        "removed_ingredients": [],
    }
    app.run(timeout=10)

    assert [message.name for message in app.chat_message] == ["user", "assistant"]
    assert app.chat_message[0].markdown[0].value == "Чим замінити куряче філе?"
    assert app.chat_message[1].markdown[0].value == "Можна використати філе індички."
    assert not any("Оновлення після обговорення" in element.value for element in app.info)
    changed_rows = [
        element.value
        for element in app.markdown
        if "chef-recipe-row--changed" in element.value
    ]
    assert any("філе індички — 500 г" in row for row in changed_rows)
    assert any(
        'data-reason="Ви попросили замінити курятину на індичку."' in row
        and 'tabindex="0"' in row
        for row in changed_rows
    )


def test_follow_up_submission_preserves_user_message_when_api_is_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run(timeout=10)
    app.session_state["current_recipe"] = {
        "id": "chicken-potatoes",
        "name": "курка з картоплею",
        "time_minutes": 55,
        "servings": 4,
        "ingredients": [],
        "steps": [],
    }
    app.run(timeout=10)

    app.chat_input[0].set_value("Заміни куряче філе").run(timeout=10)

    assert [message.name for message in app.chat_message] == ["user", "assistant"]
    assert app.chat_message[0].markdown[0].value == "Заміни куряче філе"
    assert "OPENAI_API_KEY" in app.chat_message[1].markdown[0].value
    assert app.session_state["current_recipe"]["id"] == "chicken-potatoes"
    assert app.session_state["recipe_changes"] == {
        "ingredients": [],
        "steps": [],
        "removed_ingredients": [],
    }


def test_successful_follow_up_updates_transcript_and_canonical_result(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = AppTest.from_file("app.py").run(timeout=10)
    app.session_state["agent"] = FakeFollowUpAgent()
    app.session_state["current_recipe"] = {
        "id": "chicken-potatoes",
        "name": "курка з картоплею",
        "time_minutes": 55,
        "servings": 4,
        "ingredients": [
            {"name": "куряче філе", "quantity": 500, "unit": "г", "note": None},
            {"name": "картопля", "quantity": 700, "unit": "г", "note": None},
        ],
        "steps": ["Наріжте курку, картоплю та моркву.", "Запікайте 45 хвилин."],
    }
    app.run(timeout=10)

    app.chat_input[0].set_value("Заміни куряче філе на індичку").run(timeout=10)

    answer = "Готово — рецепт оновлено вище."
    assert [message.name for message in app.chat_message] == ["user", "assistant"]
    assert app.chat_message[0].markdown[0].value == "Заміни куряче філе на індичку"
    assert app.chat_message[1].markdown[0].value == answer
    assert "Ось повний рецепт" not in app.chat_message[1].markdown[0].value
    assert app.session_state["current_recipe"]["ingredients"][0]["name"] == "філе індички"
    assert app.session_state["current_recipe"]["steps"][0] == "Наріжте індичку, картоплю та моркву."
    assert app.session_state["recipe_changes"]["ingredients"] == [
        {
            "name": "філе індички",
            "reason": "Ви попросили замінити курятину на індичку.",
        }
    ]
    assert not any(answer in element.value for element in app.info)


def test_second_follow_up_remains_available_after_a_completed_first_turn(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = AppTest.from_file("app.py").run(timeout=10)
    app.session_state["agent"] = TwoTurnFollowUpAgent()
    app.session_state["current_recipe"] = {
        "id": "chicken-potatoes",
        "name": "курка з картоплею",
        "time_minutes": 55,
        "servings": 4,
        "ingredients": [],
        "steps": [],
    }
    app.run(timeout=10)

    app.chat_input[0].set_value("Перше уточнення").run(timeout=10)
    assert app.session_state["follow_up_phase"] == "complete"
    assert app.chat_input[0].disabled is False

    app.chat_input[0].set_value("Друге уточнення").run(timeout=10)

    assert app.session_state["follow_up_phase"] == "complete"
    assert [message.name for message in app.chat_message] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert app.chat_message[3].markdown[0].value == "Друга відповідь."


def test_inline_change_styles_support_hover_and_keyboard_explanations() -> None:
    assert ".chef-recipe-row--changed:hover::after" in PAGE_STYLE
    assert ".chef-recipe-row--changed:focus-visible::after" in PAGE_STYLE
    assert "content: attr(data-reason)" in PAGE_STYLE
    assert ".st-key-recipe-result-updated" in PAGE_STYLE


def test_recipe_columns_stack_explicitly_on_mobile() -> None:
    mobile_styles = PAGE_STYLE.split("@media (max-width: 720px)", 1)[1]
    assert '.st-key-recipe-result-updated [data-testid="stHorizontalBlock"]' in mobile_styles
    assert "flex-direction: column !important" in mobile_styles
    assert '.st-key-recipe-result-updated [data-testid="stColumn"]' in mobile_styles
    assert "width: 100% !important" in mobile_styles
    assert ".chef-recipe-row--changed::after" in mobile_styles
    assert "max-width: 100%" in mobile_styles


def test_styles_use_native_placeholder_only() -> None:
    assert 'content: "Додати продукт"' not in PAGE_STYLE


def test_styles_distinguish_disabled_primary_action() -> None:
    assert "button:disabled" in PAGE_STYLE


def test_multiselect_input_remains_in_the_flex_layout() -> None:
    rule = re.search(
        r'div:has\(> input\[role="combobox"\]\) \{(?P<body>.*?)\n\}',
        PAGE_STYLE,
        re.DOTALL,
    )
    assert rule is not None
    assert "position: relative" in rule.group("body")


def test_mobile_input_resets_the_desktop_flex_basis() -> None:
    assert "flex: 1 0 100% !important" in PAGE_STYLE


def test_mobile_ingredient_tags_use_full_width() -> None:
    mobile_styles = PAGE_STYLE.split("@media (max-width: 720px)", 1)[1]
    tag_rule = re.search(
        r'\[data-testid="stMultiSelect"\] \[data-baseweb="tag"\] \{(?P<body>.*?)\n  \}',
        mobile_styles,
        re.DOTALL,
    )
    assert tag_rule is not None
    assert "flex: 1 1 100%" in tag_rule.group("body")
    assert "width: 100% !important" in tag_rule.group("body")


def test_search_controls_share_one_responsive_surface() -> None:
    assert ".st-key-ingredient-search" in PAGE_STYLE
    assert '[data-baseweb="tag"]:nth-child' not in PAGE_STYLE


def test_ingredient_remove_control_has_a_clear_button_target() -> None:
    rule = re.search(
        r'\[data-baseweb="tag"\] > span\[role="presentation"\] \{(?P<body>.*?)\n\}',
        PAGE_STYLE,
        re.DOTALL,
    )
    assert rule is not None
    body = rule.group("body")
    assert "width: 2rem" in body
    assert "height: 2rem" in body
    assert "border-radius: 999px" in body
    assert "cursor: pointer" in body


def test_ingredient_remove_control_has_hover_and_focus_states() -> None:
    assert 'span[role="presentation"]:hover {' in PAGE_STYLE
    assert "background: var(--chef-accent)" in PAGE_STYLE
    assert 'span[role="presentation"]:hover svg {' in PAGE_STYLE
    assert "fill: #fff" in PAGE_STYLE
    assert '[data-baseweb="tag"]:focus-visible {' in PAGE_STYLE
    assert "outline: 3px solid rgb(228 71 51 / 25%)" in PAGE_STYLE


def test_search_action_is_compact_on_desktop_and_stacks_on_mobile() -> None:
    desktop_rule = re.search(
        r'\.st-key-ingredient-search \[data-testid="stColumn"\]:last-child \{(?P<body>.*?)\n\}',
        PAGE_STYLE,
        re.DOTALL,
    )
    assert desktop_rule is not None
    assert "flex: 0 0 clamp(" in desktop_rule.group("body")

    mobile_styles = PAGE_STYLE.split("@media (max-width: 720px)", 1)[1]
    assert "flex-direction: column !important" in mobile_styles
    assert "width: 100% !important" in mobile_styles


def test_desktop_search_action_compensates_multiselect_bottom_inset() -> None:
    assert "@media (min-width: 721px)" in PAGE_STYLE
    desktop_styles = PAGE_STYLE.split("@media (min-width: 721px)", 1)[1].split(
        "@media (max-width: 720px)", 1
    )[0]
    assert ".st-key-ingredient-search-button" in desktop_styles
    assert "padding-bottom: 0.375rem" in desktop_styles


def test_submit_without_api_key_shows_setup_error_and_preserves_selection(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    app.button[0].click().run()
    assert not app.exception
    assert "OPENAI_API_KEY" in app.error[0].value
    assert app.multiselect[0].value == ["куряче філе", "картопля", "морква"]
    assert app.session_state["search_phase"] == "error"
    assert app.session_state["pending_search"] is False
