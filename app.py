from __future__ import annotations

import copy
import logging
import os
from collections.abc import Mapping
from html import escape
from typing import Any

import streamlit as st
from langchain.messages import HumanMessage

from chefbot import MissingAPIKeyError, ToolEvent, create_chefbot, run_chefbot
from chefbot.services import format_ingredient, known_ingredients, normalize_text


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
  --chef-change-bg: #fff0eb;
  --chef-change-border: #f0a396;
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
.stButton button[kind="primary"] {
  background: var(--chef-accent);
  border-color: var(--chef-accent);
  color: white;
  min-height: 4.3rem;
  border-radius: 0.65rem;
  font-size: 1.05rem;
  font-weight: 700;
}
.stButton button[kind="primary"] p {
  color: #fff !important;
  font-size: 1.25rem !important;
  font-weight: 700 !important;
}
.stButton button[kind="primary"]:hover {
  background: var(--chef-accent-hover);
  border-color: var(--chef-accent-hover);
}
.stButton button:disabled,
.stButton button:disabled:hover {
  background: #eee6e0 !important;
  border-color: #ded3cb !important;
  color: #7a716b !important;
  cursor: not-allowed;
  opacity: 1 !important;
}
.stButton button:disabled p {
  color: #7a716b !important;
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
.st-key-recipe-result,
.st-key-recipe-result-updated {
  margin-top: 1.25rem;
}
.st-key-recipe-result-updated {
  padding: 1.25rem 1.4rem 1.4rem;
  border: 1px solid var(--chef-change-border);
  border-radius: 1rem;
  background: rgb(255 255 255 / 60%);
  box-shadow: 0 0.5rem 1.5rem rgb(83 47 38 / 6%);
}
.chef-recipe-update-status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  width: fit-content;
  margin-bottom: 0.45rem;
  padding: 0.4rem 0.65rem;
  border-radius: 999px;
  background: var(--chef-change-bg);
  color: #8f3024;
  font-size: 0.88rem;
  font-weight: 750;
}
.chef-recipe-update-status span:last-child {
  color: var(--chef-muted);
  font-weight: 500;
}
.chef-recipe-row {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  min-height: 2.2rem;
  margin: 0 -0.65rem 0.25rem;
  padding: 0.45rem 0.65rem;
  border: 1px solid transparent;
  border-radius: 0.65rem;
  line-height: 1.45;
}
.chef-recipe-marker {
  flex: 0 0 auto;
  color: var(--chef-accent);
  font-weight: 800;
}
.chef-recipe-row-text { flex: 1 1 auto; min-width: 0; }
.chef-recipe-step-number { font-weight: 750; }
.chef-recipe-change-badge {
  flex: 0 0 auto;
  margin-top: 0.05rem;
  padding: 0.16rem 0.42rem;
  border-radius: 999px;
  background: #fff;
  color: #a23b2e;
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.01em;
}
.chef-recipe-row--changed {
  border-color: var(--chef-change-border);
  background: var(--chef-change-bg);
  cursor: help;
}
.chef-recipe-row--removed .chef-recipe-row-text {
  color: var(--chef-muted);
  text-decoration: line-through;
}
.chef-recipe-row--changed::after {
  content: attr(data-reason);
  box-sizing: border-box;
  position: absolute;
  left: 0.4rem;
  top: calc(100% + 0.35rem);
  z-index: 20;
  width: max-content;
  max-width: min(24rem, calc(100vw - 3rem));
  padding: 0.55rem 0.7rem;
  border-radius: 0.55rem;
  background: #2f2a27;
  color: #fff;
  box-shadow: 0 0.6rem 1.5rem rgb(37 35 33 / 20%);
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.35;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-0.2rem);
  transition: opacity 140ms ease, transform 140ms ease;
}
.chef-recipe-row--changed:hover::after,
.chef-recipe-row--changed:focus-visible::after {
  opacity: 1;
  transform: translateY(0);
}
.chef-recipe-row--changed:focus-visible {
  outline: 3px solid rgb(228 71 51 / 24%);
  outline-offset: 2px;
}
.st-key-ingredient-search {
  margin: 1.25rem 0 1.5rem;
  padding: 1.25rem;
  border: 1px solid var(--chef-divider);
  border-radius: 1rem;
  background: rgb(255 255 255 / 72%);
}
.st-key-ingredient-search .st-key-ingredient-search-button {
  width: 100%;
}
.st-key-ingredient-search [data-testid="stHorizontalBlock"] {
  align-items: flex-end;
  gap: 1rem;
}
.st-key-ingredient-search [data-testid="stColumn"]:first-child {
  flex: 1 1 auto !important;
  min-width: 0;
}
.st-key-ingredient-search [data-testid="stColumn"]:last-child {
  flex: 0 0 clamp(11rem, 16vw, 14rem) !important;
  width: clamp(11rem, 16vw, 14rem) !important;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  min-height: 4.3rem;
  padding: 0;
  background: transparent;
  border-color: transparent;
  box-shadow: none;
  gap: 0.75rem;
}
[data-testid="stMultiSelect"] label {
  color: var(--chef-text);
  font-size: 0.95rem;
  font-weight: 700;
  margin-bottom: 0.45rem;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] > div > div:first-child {
  align-items: center;
  flex: 1 1 auto;
  width: 100%;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
  flex: 0 1 auto;
  width: auto;
  max-width: 100%;
  min-height: 4.3rem;
  padding: 0 0.75rem 0 1rem;
  background: #fff;
  color: var(--chef-text);
  border: 1px solid var(--chef-divider);
  border-radius: 0.65rem;
  justify-content: space-between;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span[title] {
  font-size: 1.05rem;
  font-weight: 500;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg { fill: var(--chef-accent); }
[data-testid="stMultiSelect"] [data-baseweb="tag"] > span[role="presentation"] {
  display: inline-flex;
  flex: 0 0 2rem;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  margin-left: 0.5rem;
  border-radius: 999px;
  background: #fbe8e4;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] > span[role="presentation"] svg {
  width: 0.8rem;
  height: 0.8rem;
  fill: var(--chef-accent);
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] > span[role="presentation"]:hover {
  background: var(--chef-accent);
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] > span[role="presentation"]:hover svg {
  fill: #fff;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"]:focus-visible {
  outline: 3px solid rgb(228 71 51 / 25%);
  outline-offset: 2px;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input[role="combobox"]) {
  flex: 1 1 17rem;
  position: relative;
  width: auto;
  min-width: 17rem;
  min-height: 4.3rem;
  padding: 0 1rem;
  background: #fff;
  border: 1px solid var(--chef-divider);
  border-radius: 0.65rem;
}
[data-testid="stMultiSelect"] input[role="combobox"]::placeholder {
  color: var(--chef-muted);
  opacity: 1;
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
@media (min-width: 721px) {
  .st-key-ingredient-search-button {
    padding-bottom: 0.375rem;
  }
}
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
  .st-key-recipe-result-updated {
    padding: 1rem;
  }
  .chef-recipe-update-status span:last-child {
    flex-basis: 100%;
  }
  .chef-recipe-change-badge {
    align-self: center;
  }
  .chef-recipe-row--changed::after {
    left: 0;
    max-width: 100%;
  }
  .st-key-recipe-result [data-testid="stHorizontalBlock"],
  .st-key-recipe-result-updated [data-testid="stHorizontalBlock"] {
    flex-direction: column !important;
    gap: 1rem !important;
  }
  .st-key-recipe-result [data-testid="stColumn"],
  .st-key-recipe-result-updated [data-testid="stColumn"] {
    flex: 1 1 auto !important;
    width: 100% !important;
  }
  .st-key-ingredient-search {
    margin-top: 1rem;
    padding: 0.8rem;
  }
  .st-key-ingredient-search [data-testid="stHorizontalBlock"] {
    align-items: stretch !important;
    flex-direction: column !important;
    gap: 0.75rem !important;
  }
  .st-key-ingredient-search [data-testid="stColumn"] {
    flex: 1 1 auto !important;
    width: 100% !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div {
    width: 100% !important;
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div:first-child {
    align-items: center !important;
    flex: 1 0 100% !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 0.625rem;
    min-width: 100% !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div:last-child {
    display: none !important;
  }
  [data-testid="stMultiSelect"] [data-baseweb="tag"] {
    flex: 1 1 100%;
    width: 100% !important;
    min-width: 100%;
  }
  [data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input[role="combobox"]) {
    width: 100% !important;
    min-width: 100% !important;
    flex: 1 0 100% !important;
  }
  [data-testid="stBottom"] > div {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
}
</style>
"""

SEARCHING_ICON_STYLE = """
<style>
@keyframes chef-search-spin {
  to { transform: rotate(360deg); }
}
.st-key-ingredient-search-button [data-testid="stIconMaterial"] {
  display: inline-block;
  animation: chef-search-spin 0.8s linear infinite;
  transform-origin: center;
}
@media (prefers-reduced-motion: reduce) {
  .st-key-ingredient-search-button [data-testid="stIconMaterial"] {
    animation: none;
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


def empty_recipe_changes() -> dict[str, list[dict[str, Any]]]:
    return {
        "ingredients": [],
        "steps": [],
        "removed_ingredients": [],
    }


def _remember_change(
    changes: dict[str, list[dict[str, Any]]],
    group: str,
    identity: str | int,
    reason: str,
) -> None:
    identity_key = "index" if group == "steps" else "name"
    changes[group] = [
        item for item in changes[group] if item.get(identity_key) != identity
    ]
    changes[group].append({identity_key: identity, "reason": reason})


def apply_recipe_edits(
    recipe: dict[str, Any],
    events: list[ToolEvent],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Apply verified recipe_editor patches and describe only this turn's changes."""
    updated = copy.deepcopy(recipe)
    changes = empty_recipe_changes()

    for event in events:
        if event.name != "recipe_editor" or event.status != "ok":
            continue
        edit = event.artifact
        action = str(edit.get("action", ""))
        ingredient_name = str(edit.get("ingredient", "")).strip()
        replacement = str(edit.get("replacement", "")).strip()
        reason = str(edit.get("reason", "")).strip()
        if not reason:
            continue

        ingredient_applied = action == "update_step"
        ingredient_index = next(
            (
                index
                for index, item in enumerate(updated.get("ingredients", []))
                if normalize_text(str(item.get("name", "")))
                == normalize_text(ingredient_name)
            ),
            None,
        )

        if action == "add" and ingredient_name:
            if ingredient_index is None:
                updated["ingredients"].append(
                    {
                        "name": ingredient_name,
                        "quantity": edit.get("quantity"),
                        "unit": edit.get("unit"),
                        "note": edit.get("note"),
                    }
                )
            else:
                existing = updated["ingredients"][ingredient_index]
                if edit.get("quantity") is not None:
                    existing["quantity"] = edit["quantity"]
                    existing["unit"] = edit.get("unit")
                if edit.get("note") is not None:
                    existing["note"] = edit["note"]
            _remember_change(changes, "ingredients", ingredient_name, reason)
            ingredient_applied = True

        elif action == "replace" and ingredient_index is not None and replacement:
            existing = updated["ingredients"][ingredient_index]
            existing["name"] = replacement
            if edit.get("quantity") is not None:
                existing["quantity"] = edit["quantity"]
                existing["unit"] = edit.get("unit")
            if edit.get("note") is not None:
                existing["note"] = edit["note"]
            _remember_change(changes, "ingredients", replacement, reason)
            ingredient_applied = True

        elif action == "remove" and ingredient_index is not None:
            removed = updated["ingredients"].pop(ingredient_index)
            _remember_change(
                changes,
                "removed_ingredients",
                str(removed["name"]),
                reason,
            )
            ingredient_applied = True

        if not ingredient_applied:
            continue
        step_number = edit.get("step_number")
        step_text = str(edit.get("step_text", "")).strip()
        if (
            isinstance(step_number, int)
            and 1 <= step_number <= len(updated.get("steps", []))
            and step_text
        ):
            step_index = step_number - 1
            updated["steps"][step_index] = step_text
            _remember_change(changes, "steps", step_index, reason)

    return updated, changes


def _has_recipe_changes(changes: dict[str, list[dict[str, Any]]]) -> bool:
    return any(changes.values())


def _streamlit_secrets() -> Mapping[str, Any]:
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return {}
    return {"OPENAI_API_KEY": api_key} if api_key else {}


def _init_state() -> None:
    defaults = {
        "ingredients": ["куряче філе", "картопля", "морква"],
        "search_phase": "idle",
        "pending_search": False,
        "messages": [],
        "agent": None,
        "current_recipe": None,
        "last_events": [],
        "last_answer": "",
        "error": "",
        "chat_history": [],
        "recipe_changes": empty_recipe_changes(),
        "last_recipe_edit_applied": False,
        "pending_follow_up": None,
        "follow_up_phase": "idle",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_search_result() -> None:
    st.session_state.messages = []
    st.session_state.current_recipe = None
    st.session_state.last_events = []
    st.session_state.last_answer = ""
    st.session_state.error = ""
    st.session_state.chat_history = []
    st.session_state.recipe_changes = empty_recipe_changes()
    st.session_state.last_recipe_edit_applied = False
    st.session_state.pending_follow_up = None
    st.session_state.follow_up_phase = "idle"


def _ingredients_changed() -> None:
    _clear_search_result()
    st.session_state.search_phase = "idle"
    st.session_state.pending_search = False


def _queue_recipe_search() -> None:
    if not st.session_state.ingredients:
        return
    _clear_search_result()
    st.session_state.search_phase = "searching"
    st.session_state.pending_search = True


def _agent(api_key: str):
    if st.session_state.agent is None:
        st.session_state.agent = create_chefbot(api_key=api_key)
    return st.session_state.agent


def _perform_query(query: str, api_key: str, reset: bool) -> bool:
    st.session_state.last_recipe_edit_applied = False
    previous_messages = [] if reset else list(st.session_state.messages)
    request_messages = [*previous_messages, HumanMessage(content=query)]
    try:
        result = run_chefbot(_agent(api_key), request_messages)
    except MissingAPIKeyError:
        st.session_state.error = "Додайте OPENAI_API_KEY у змінні середовища або Streamlit secrets."
        return False
    except Exception:
        LOGGER.exception("ChefBot request failed")
        st.session_state.error = "ChefBot тимчасово не відповідає. Повторіть запит за хвилину."
        return False

    recipe = latest_recipe(result.tool_events)
    st.session_state.messages = result.messages
    st.session_state.last_events = result.tool_events
    st.session_state.last_answer = result.answer
    st.session_state.error = ""
    if recipe is not None:
        st.session_state.current_recipe = recipe
        st.session_state.recipe_changes = empty_recipe_changes()
    elif not reset and st.session_state.current_recipe:
        updated_recipe, changes = apply_recipe_edits(
            st.session_state.current_recipe,
            result.tool_events,
        )
        if _has_recipe_changes(changes):
            st.session_state.current_recipe = updated_recipe
            st.session_state.recipe_changes = changes
            st.session_state.last_recipe_edit_applied = True
    elif reset:
        st.session_state.current_recipe = None
    return True


def _run_pending_recipe_search() -> None:
    if not st.session_state.pending_search:
        return

    st.session_state.pending_search = False
    api_key = get_api_key(_streamlit_secrets())
    if not api_key:
        st.session_state.error = (
            "Додайте OPENAI_API_KEY у змінні середовища або `.streamlit/secrets.toml`."
        )
        st.session_state.search_phase = "error"
        st.rerun()
        return

    query = "Знайди страву з продуктів: " + ", ".join(st.session_state.ingredients) + "."
    _perform_query(query, api_key, reset=True)
    st.session_state.search_phase = "error" if st.session_state.error else "complete"
    st.rerun()


def _queue_follow_up(message: str) -> None:
    content = message.strip()
    if not content:
        return
    st.session_state.chat_history = [
        *st.session_state.chat_history,
        {"role": "user", "content": content},
    ]
    st.session_state.pending_follow_up = content
    st.session_state.follow_up_phase = "responding"
    st.session_state.error = ""


def _run_pending_follow_up() -> None:
    query = st.session_state.pending_follow_up
    if not query:
        return

    st.session_state.pending_follow_up = None
    api_key = get_api_key(_streamlit_secrets())
    if not api_key:
        message = "Додайте OPENAI_API_KEY перед продовженням розмови."
        st.session_state.error = message
        st.session_state.chat_history = [
            *st.session_state.chat_history,
            {"role": "assistant", "content": message},
        ]
        st.session_state.follow_up_phase = "error"
        st.rerun()
        return

    succeeded = _perform_query(query, api_key, reset=False)
    if succeeded:
        if st.session_state.last_recipe_edit_applied:
            answer = "Готово — рецепт оновлено вище."
        else:
            answer = st.session_state.last_answer.strip() or "Рецепт оновлено."
        st.session_state.chat_history = [
            *st.session_state.chat_history,
            {"role": "assistant", "content": answer},
        ]
        st.session_state.follow_up_phase = "complete"
    else:
        message = st.session_state.error or "ChefBot не зміг оновити рецепт."
        st.session_state.chat_history = [
            *st.session_state.chat_history,
            {"role": "assistant", "content": message},
        ]
        st.session_state.follow_up_phase = "error"
    st.rerun()


def _render_tool_events(events: list[ToolEvent]) -> None:
    for event in events:
        if event.name == "recipe_editor":
            continue
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


def _change_reason(
    changes: dict[str, list[dict[str, Any]]],
    group: str,
    identity: str | int,
) -> str:
    identity_key = "index" if group == "steps" else "name"
    for item in changes.get(group, []):
        candidate = item.get(identity_key)
        if group == "steps" and candidate == identity:
            return str(item.get("reason", ""))
        if group != "steps" and normalize_text(str(candidate)) == normalize_text(str(identity)):
            return str(item.get("reason", ""))
    return ""


def _render_recipe_row(
    text: str,
    reason: str = "",
    *,
    marker: str = "•",
    removed: bool = False,
) -> None:
    classes = ["chef-recipe-row"]
    attributes = ""
    badge = ""
    if reason:
        classes.append("chef-recipe-row--changed")
        if removed:
            classes.append("chef-recipe-row--removed")
        safe_reason = escape(reason, quote=True)
        safe_label = escape(f"{text}. Причина зміни: {reason}", quote=True)
        attributes = (
            f' tabindex="0" data-reason="{safe_reason}" aria-label="{safe_label}"'
        )
        badge_text = "Видалено" if removed else "Оновлено"
        badge = f'<span class="chef-recipe-change-badge">{badge_text}</span>'
    st.markdown(
        f'<div class="{" ".join(classes)}"{attributes}>'
        f'<span class="chef-recipe-marker" aria-hidden="true">{escape(marker)}</span>'
        f'<span class="chef-recipe-row-text">{escape(text)}</span>'
        f"{badge}</div>",
        unsafe_allow_html=True,
    )


def _render_recipe(
    recipe: dict[str, Any],
    changes: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    changes = changes or empty_recipe_changes()
    if _has_recipe_changes(changes):
        st.markdown(
            '<div class="chef-recipe-update-status">'
            '<span>Рецепт оновлено</span>'
            '<span>Наведіть або сфокусуйте підсвічений рядок, щоб побачити причину.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
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
            _render_recipe_row(
                format_ingredient(ingredient),
                _change_reason(changes, "ingredients", ingredient["name"]),
            )
        for removed in changes.get("removed_ingredients", []):
            removed_name = str(removed.get("name", ""))
            _render_recipe_row(
                removed_name,
                str(removed.get("reason", "")),
                marker="−",
                removed=True,
            )

    with steps_column:
        st.subheader("Приготування")
        for index, step in enumerate(recipe["steps"], 1):
            _render_recipe_row(
                f"{index}. {step}",
                _change_reason(changes, "steps", index - 1),
                marker="",
            )


def _render_discussion() -> None:
    st.divider()
    st.subheader("Обговорення рецепта")
    if not st.session_state.chat_history:
        st.caption("Поставте запитання або уточніть рецепт — відповідь оновить результат вище.")
    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
    if st.session_state.follow_up_phase == "responding":
        with st.chat_message("assistant"):
            st.status(
                "ChefBot оновлює рецепт…",
                state="running",
                expanded=False,
                type="compact",
            )


def main() -> None:
    st.set_page_config(
        page_title="ChefBot",
        page_icon=":material/skillet:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(PAGE_STYLE, unsafe_allow_html=True)
    _init_state()
    if st.session_state.search_phase == "searching":
        st.markdown(SEARCHING_ICON_STYLE, unsafe_allow_html=True)

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

    with st.container(key="ingredient-search"):
        ingredients_column, action_column = st.columns(
            [5, 1],
            gap="medium",
            vertical_alignment="bottom",
        )
        with ingredients_column:
            selected = st.multiselect(
                "Продукти",
                options=known_ingredients(),
                placeholder="Додати продукт",
                accept_new_options=True,
                max_selections=12,
                key="ingredients",
                on_change=_ingredients_changed,
                label_visibility="visible",
            )
        searching = st.session_state.search_phase == "searching"
        with action_column:
            st.button(
                "Шукаємо страву…" if searching else "Знайти страву",
                type="primary",
                use_container_width=True,
                disabled=not selected or searching,
                key="ingredient-search-button",
                icon=":material/progress_activity:" if searching else ":material/search:",
                on_click=_queue_recipe_search,
            )

        if not selected:
            st.caption("Додайте хоча б один продукт.")
        elif searching:
            st.status(
                "ChefBot шукає перевірений рецепт…",
                state="running",
                expanded=False,
                type="compact",
            )

    _run_pending_recipe_search()

    if st.session_state.error:
        st.error(st.session_state.error)

    _render_tool_events(st.session_state.last_events)
    if st.session_state.current_recipe:
        recipe_changes = st.session_state.recipe_changes
        recipe_container_key = (
            "recipe-result-updated"
            if _has_recipe_changes(recipe_changes)
            else "recipe-result"
        )
        with st.container(key=recipe_container_key):
            _render_recipe(st.session_state.current_recipe, changes=recipe_changes)
    elif any(event.name == "recipe_search" for event in st.session_state.last_events):
        st.info("Спробуйте змінити продукти або сформулювати інший запит.")

    show_answer = st.session_state.last_answer and not st.session_state.current_recipe
    if show_answer:
        with st.expander("Відповідь ChefBot"):
            st.write(st.session_state.last_answer)

    if st.session_state.current_recipe or st.session_state.last_answer:
        _render_discussion()
        follow_up = st.chat_input(
            "Уточніть рецепт або запитайте про заміну…",
            key="chef-follow-up",
            accept_audio=False,
            disabled=st.session_state.follow_up_phase == "responding",
        )
        if follow_up:
            _queue_follow_up(str(follow_up))
            st.rerun()
        _run_pending_follow_up()


if __name__ == "__main__":
    main()
