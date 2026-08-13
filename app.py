from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import streamlit as st
from langchain.messages import HumanMessage

from chefbot import MissingAPIKeyError, ToolEvent, create_chefbot, run_chefbot
from chefbot.services import format_ingredient, known_ingredients


LOGGER = logging.getLogger(__name__)

PAGE_STYLE = """
<style>
:root {
  --chef-bg: #fbf8f4;
  --chef-text: #252321;
  --chef-muted: #726b66;
  --chef-accent: #e44733;
  --chef-accent-hover: #ca3828;
  --chef-success: #3b9b58;
  --chef-divider: #e5ddd6;
}

.stApp {
  background: var(--chef-bg);
  color: var(--chef-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.block-container {
  max-width: 1487px;
  padding: 1.35rem 3.5rem 7rem;
}
h1, h2, h3, p, label { color: var(--chef-text); }
h1 {
  font-size: clamp(3rem, 4vw, 3.75rem) !important;
  line-height: 1.05 !important;
  letter-spacing: -0.045em !important;
  font-weight: 760 !important;
  margin-top: 4.2rem;
  margin-bottom: 0.8rem;
}
h2 {
  font-size: 2.5rem !important;
  line-height: 1.1 !important;
  letter-spacing: -0.035em;
}
ul li::marker { color: var(--chef-accent); }
[data-testid="stHeader"] { display: none; }
[data-testid="stForm"] { border: 0; padding: 0; }
div[data-testid="stForm"] { margin-top: 0.9rem; }
div[data-testid="stFormSubmitButton"] button,
.stButton button[kind="primary"] {
  background: var(--chef-accent);
  border-color: var(--chef-accent);
  color: white;
  min-height: 4.3rem;
  border-radius: 0.65rem;
  font-size: 1.05rem;
  font-weight: 700;
}
div[data-testid="stFormSubmitButton"] button p,
.stButton button[kind="primary"] p {
  color: #fff !important;
  font-size: 1.25rem !important;
  font-weight: 700 !important;
}
div[data-testid="stFormSubmitButton"] button:hover,
.stButton button[kind="primary"]:hover {
  background: var(--chef-accent-hover);
  border-color: var(--chef-accent-hover);
}
.chef-header {
  display: flex;
  min-height: 2.25rem;
  align-items: center;
  gap: 1rem;
  margin-left: -3.5rem;
  margin-right: -3.5rem;
  padding: 0 3.5rem 0.75rem 2.5rem;
  border-bottom: 1px solid var(--chef-divider);
}
.chef-logo {
  color: var(--chef-accent);
  font-family: "Material Symbols Rounded";
  font-size: 2.25rem;
  font-weight: 400;
  line-height: 1;
}
.chef-brand { font-size: 2rem; font-weight: 800; letter-spacing: -0.04em; }
.chef-header-divider { width: 1px; height: 1.9rem; background: var(--chef-divider); margin: 0 0.75rem; }
.chef-tagline { color: var(--chef-text); font-size: 1.05rem; }
.chef-tool {
  color: var(--chef-text);
  font-weight: 500;
  padding: 1rem 0;
  border-top: 1px solid var(--chef-divider);
  border-bottom: 1px solid var(--chef-divider);
}
.chef-tool-icon {
  color: var(--chef-success);
  font-family: "Material Symbols Rounded";
  font-size: 1.6rem;
  margin-right: 0.65rem;
  vertical-align: -0.25rem;
}
.chef-muted { color: var(--chef-muted); font-size: 1.25rem !important; }
.chef-meta {
  display: flex;
  align-items: center;
  gap: 3rem;
  margin: 0.8rem 0 2rem;
  font-weight: 700;
}
.chef-meta-item { display: inline-flex; align-items: center; gap: 0.45rem; }
.chef-meta-icon {
  color: var(--chef-accent);
  font-family: "Material Symbols Rounded";
  font-size: 1.5rem;
  font-weight: 400;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  min-height: 4.3rem;
  padding: 0;
  background: transparent;
  border-color: transparent;
  box-shadow: none;
  gap: 0.75rem;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
  width: 15.25rem;
  min-height: 4.3rem;
  padding: 0 1rem;
  background: #fff;
  color: var(--chef-text);
  border: 1px solid var(--chef-divider);
  border-radius: 0.65rem;
  justify-content: space-between;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"]:first-child { width: 17rem; }
[data-testid="stMultiSelect"] [data-baseweb="tag"]:nth-child(3) { width: 14.6rem; }
[data-testid="stMultiSelect"] [data-baseweb="tag"] span[title] {
  font-size: 1.05rem;
  font-weight: 500;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg { fill: var(--chef-accent); }
[data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input[role="combobox"]) {
  position: relative;
  min-width: 17rem;
  min-height: 4.3rem;
  padding: 0 1rem;
  background: #fff;
  border: 1px solid var(--chef-divider);
  border-radius: 0.65rem;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input[role="combobox"])::after {
  content: "Додати продукт";
  position: absolute;
  inset: 1.3rem auto auto 1rem;
  color: #948e89;
  font-size: 1.05rem;
  pointer-events: none;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input[role="combobox"]:focus)::after {
  display: none;
}
[data-testid="stMultiSelect"] svg[title="Clear all"],
[data-testid="stMultiSelect"] svg[title="open"] { display: none; }
[data-testid="stBottom"] > div {
  width: 100% !important;
  max-width: 100% !important;
  padding-left: 3.5rem !important;
  padding-right: 3.5rem !important;
  background: transparent !important;
}
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stBottomBlockContainer"] {
  width: 100% !important;
  max-width: 100% !important;
  padding: 0 0 1.65rem !important;
}
[data-testid="stChatInput"] {
  min-height: 5rem;
  border-color: var(--chef-divider);
  border-radius: 0.75rem;
  background: #fff;
}
[data-testid="stChatInputTextArea"] { padding-top: 1.65rem; font-size: 1.05rem; }
[data-testid="stChatInputSubmitButton"] {
  width: 3.25rem;
  height: 3.25rem;
  margin: 0.75rem;
  border-radius: 0.6rem;
  background: var(--chef-accent) !important;
  color: #fff !important;
  opacity: 1 !important;
}
hr { border-color: var(--chef-divider); }
@media (max-width: 720px) {
  .block-container { padding: 1rem 1rem 7rem; }
  h1 {
    font-size: 3rem !important;
    margin-top: 2.5rem;
  }
  .chef-header {
    align-items: center;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin-left: -1rem;
    margin-right: -1rem;
    padding-left: 1rem;
    padding-right: 1rem;
  }
  .chef-header-divider { display: none; }
  .chef-brand { font-size: 1.6rem; }
  .chef-tagline {
    flex-basis: 100%;
    font-size: 0.95rem;
  }
  .chef-meta { gap: 1.5rem; }
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div {
    width: 100% !important;
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div {
    align-items: stretch !important;
    flex: 1 0 100% !important;
    flex-direction: column !important;
    min-width: 100% !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div:last-child {
    display: none !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="tag"],
  [data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input[role="combobox"]) {
    width: 100% !important;
    min-width: 100%;
  }
  [data-testid="stBottom"] > div {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
}
</style>
"""


def get_api_key(secrets: Mapping[str, Any] | None = None) -> str | None:
    return os.environ.get("OPENAI_API_KEY") or (
        secrets.get("OPENAI_API_KEY") if secrets is not None else None
    )


def latest_recipe(events: list[ToolEvent]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.name != "recipe_search" or event.status != "ok":
            continue
        matches = event.artifact.get("matches", [])
        if matches:
            return matches[0]["recipe"]
    return None


def _streamlit_secrets() -> Mapping[str, Any]:
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return {}
    return {"OPENAI_API_KEY": api_key} if api_key else {}


def _init_state() -> None:
    defaults = {
        "ingredients": ["куряче філе", "картопля", "морква"],
        "messages": [],
        "agent": None,
        "current_recipe": None,
        "last_events": [],
        "last_answer": "",
        "error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _agent(api_key: str):
    if st.session_state.agent is None:
        st.session_state.agent = create_chefbot(api_key=api_key)
    return st.session_state.agent


def _perform_query(query: str, api_key: str, reset: bool) -> None:
    previous_messages = [] if reset else list(st.session_state.messages)
    request_messages = [*previous_messages, HumanMessage(content=query)]
    try:
        result = run_chefbot(_agent(api_key), request_messages)
    except MissingAPIKeyError:
        st.session_state.error = "Додайте OPENAI_API_KEY у змінні середовища або Streamlit secrets."
        return
    except Exception:
        LOGGER.exception("ChefBot request failed")
        st.session_state.error = "ChefBot тимчасово не відповідає. Повторіть запит за хвилину."
        return

    recipe = latest_recipe(result.tool_events)
    st.session_state.messages = result.messages
    st.session_state.last_events = result.tool_events
    st.session_state.last_answer = result.answer
    st.session_state.error = ""
    if recipe is not None:
        st.session_state.current_recipe = recipe
    elif reset:
        st.session_state.current_recipe = None


def _render_tool_events(events: list[ToolEvent]) -> None:
    for event in events:
        if event.status == "ok":
            st.markdown(
                '<div class="chef-tool">'
                '<span class="chef-tool-icon" aria-hidden="true">check_circle</span>'
                f"{event.name} · виконано</div>",
                unsafe_allow_html=True,
            )
        elif event.status == "not_found":
            st.warning(f"{event.name}: у локальній базі немає відповідних даних.")
        elif event.status == "error":
            st.error(f"{event.name}: інструмент тимчасово недоступний.")


def _render_recipe(recipe: dict[str, Any]) -> None:
    st.header(recipe["name"].capitalize())
    st.markdown(
        '<div class="chef-meta">'
        '<span class="chef-meta-item"><span class="chef-meta-icon" aria-hidden="true">schedule</span>'
        f"{recipe['time_minutes']} хвилин</span>"
        '<span class="chef-meta-item"><span class="chef-meta-icon" aria-hidden="true">group</span>'
        f"{recipe['servings']} порції</span></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    ingredients_column, steps_column = st.columns([2, 3], gap="large")
    with ingredients_column:
        st.subheader("Інгредієнти")
        for ingredient in recipe["ingredients"]:
            st.markdown(f"- {format_ingredient(ingredient)}")

    with steps_column:
        st.subheader("Приготування")
        for index, step in enumerate(recipe["steps"], 1):
            st.markdown(f"**{index}.** {step}")


def main() -> None:
    st.set_page_config(
        page_title="ChefBot",
        page_icon=":material/skillet:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(PAGE_STYLE, unsafe_allow_html=True)
    _init_state()

    st.markdown(
        '<div class="chef-header"><span class="chef-logo" aria-hidden="true">chef_hat</span>'
        '<span class="chef-brand">ChefBot</span><span class="chef-header-divider"></span>'
        '<span class="chef-tagline">Ваш AI-помічник на кухні</span></div>',
        unsafe_allow_html=True,
    )
    st.title("Що є у вас сьогодні?")
    st.markdown(
        '<p class="chef-muted">Вкажіть продукти, які маєте, і ChefBot підбере відповідну страву.</p>',
        unsafe_allow_html=True,
    )

    with st.form("ingredient-search", border=False):
        ingredients_column, action_column = st.columns([4, 1], vertical_alignment="bottom")
        with ingredients_column:
            selected = st.multiselect(
                "Продукти",
                options=known_ingredients(),
                default=st.session_state.ingredients,
                placeholder="Додати продукт",
                accept_new_options=True,
                max_selections=12,
                key="ingredient-picker",
                label_visibility="collapsed",
            )
        with action_column:
            submitted = st.form_submit_button(
                "Знайти страву",
                type="primary",
                use_container_width=True,
                disabled=not selected,
            )

    if submitted:
        st.session_state.ingredients = selected
        api_key = get_api_key(_streamlit_secrets())
        if not api_key:
            st.session_state.error = "Додайте OPENAI_API_KEY у змінні середовища або `.streamlit/secrets.toml`."
        else:
            query = "Знайди страву з продуктів: " + ", ".join(selected) + "."
            with st.spinner("ChefBot шукає перевірений рецепт..."):
                _perform_query(query, api_key, reset=True)

    if st.session_state.error:
        st.error(st.session_state.error)

    _render_tool_events(st.session_state.last_events)
    if st.session_state.current_recipe:
        _render_recipe(st.session_state.current_recipe)
    elif any(event.name == "recipe_search" for event in st.session_state.last_events):
        st.info("Спробуйте змінити продукти або сформулювати інший запит.")

    show_answer = st.session_state.last_answer and (
        not st.session_state.current_recipe
        or any(event.name != "recipe_search" for event in st.session_state.last_events)
    )
    if show_answer:
        with st.expander("Відповідь ChefBot"):
            st.write(st.session_state.last_answer)

    with st.container():
        follow_up = st.chat_input(
            "Уточніть рецепт або запитайте про заміну…",
            key="chef-follow-up",
            accept_audio=False,
        )
    if follow_up:
        api_key = get_api_key(_streamlit_secrets())
        if not api_key:
            st.session_state.error = "Додайте OPENAI_API_KEY перед продовженням розмови."
        else:
            with st.spinner("ChefBot уточнює відповідь..."):
                _perform_query(follow_up, api_key, reset=False)
        st.rerun()


if __name__ == "__main__":
    main()
