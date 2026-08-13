import re

from streamlit.testing.v1 import AppTest

from app import PAGE_STYLE, get_api_key, latest_recipe
from chefbot.agent import ToolEvent


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


def test_follow_up_is_hidden_until_conversation_context_exists(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    assert not app.chat_input


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


def test_submit_without_api_key_shows_setup_error_and_preserves_selection(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    app.button[0].click().run()
    assert not app.exception
    assert "OPENAI_API_KEY" in app.error[0].value
    assert app.multiselect[0].value == ["куряче філе", "картопля", "морква"]
    assert app.session_state["search_phase"] == "error"
    assert app.session_state["pending_search"] is False
