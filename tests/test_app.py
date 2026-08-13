from streamlit.testing.v1 import AppTest

from app import get_api_key, latest_recipe
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


def test_submit_without_api_key_shows_setup_error_and_preserves_selection(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    app.button[0].click().run()
    assert not app.exception
    assert "OPENAI_API_KEY" in app.error[0].value
    assert app.multiselect[0].value == ["куряче філе", "картопля", "морква"]
