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
    assert "flex: 0 0 auto !important" in PAGE_STYLE


def test_submit_without_api_key_shows_setup_error_and_preserves_selection(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    app.button[0].click().run()
    assert not app.exception
    assert "OPENAI_API_KEY" in app.error[0].value
    assert app.multiselect[0].value == ["куряче філе", "картопля", "морква"]
