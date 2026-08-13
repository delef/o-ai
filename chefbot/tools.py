from __future__ import annotations

import re
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from chefbot.services import (
    convert_units,
    find_substitutions,
    format_ingredient,
    search_recipes,
)


class RecipeIngredientRevision(BaseModel):
    """One ingredient in the revised, user-visible final recipe."""

    name: str = Field(default="", description="Назва інгредієнта.")
    quantity: float | None = Field(
        default=None,
        description="Додатна кількість, якщо вона відома або запропонована для рецепта.",
    )
    unit: str | None = Field(
        default=None,
        description="Одиниця виміру для quantity, наприклад «г» або «шт.».",
    )
    note: str | None = Field(
        default=None,
        description="Коротка примітка, наприклад «за смаком».",
    )


class RecipeRevision(BaseModel):
    """The only accepted representation of a confirmed recipe change."""

    reason: str = Field(
        description="Коротка причина, заснована на явному проханні користувача."
    )
    ingredients: list[RecipeIngredientRevision] = Field(
        description=(
            "Повний актуальний список усіх інгредієнтів фінального рецепта, "
            "включно з незміненими."
        )
    )
    steps: list[str] = Field(
        description=(
            "Усі кроки фінального рецепта від першого до останнього, "
            "включно з незміненими."
        )
    )


def _clean_step(step: str) -> str:
    return re.sub(r"^\s*\d+[.)]\s*", "", step).strip()


def _recipe_content(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "У локальній базі не знайдено відповідного рецепта. Змініть страву, продукти або категорію пошуку."

    blocks = []
    for match in matches:
        recipe = match["recipe"]
        ingredients = ", ".join(format_ingredient(item) for item in recipe["ingredients"])
        steps = " ".join(f"{index}. {step}" for index, step in enumerate(recipe["steps"], 1))
        blocks.append(
            f"{recipe['name'].capitalize()}\n"
            f"Інгредієнти: {ingredients}\n"
            f"Час: {recipe['time_minutes']} хвилин. Порцій: {recipe['servings']}.\n"
            f"Приготування: {steps}\n"
            f"Знайдено за: {', '.join(match['match_reasons'])}"
        )
    return "\n\n".join(blocks)


@tool(response_format="content_and_artifact")
def recipe_search(query: str) -> tuple[str, dict[str, Any]]:
    """Шукай до трьох рецептів за назвою, продуктами, категорією або вимогою без глютену."""
    matches = search_recipes(query)
    artifact = {
        "kind": "recipe_search",
        "status": "ok" if matches else "not_found",
        "query": query,
        "matches": matches,
    }
    return _recipe_content(matches), artifact


@tool(response_format="content_and_artifact")
def unit_converter(
    amount: float,
    from_unit: str,
    to_unit: str,
    product: str = "",
) -> tuple[str, dict[str, Any]]:
    """Конвертуй підтримувані кулінарні одиниці; для ваги вкажи продукт, якщо його щільність важлива."""
    result = convert_units(amount, from_unit, to_unit, product or None)
    artifact = {"kind": "unit_converter", **result}

    if result["status"] == "ok":
        qualifier = "≈" if result["approximate"] else "="
        product_text = f" продукту «{result['product']}»" if result.get("product") else ""
        content = (
            f"{result['amount']:g} {result['from_unit']}{product_text} "
            f"{qualifier} {result['result']:g} {result['to_unit']}."
        )
    elif result["status"] == "clarification":
        content = "Для переведення у вагу потрібно вказати продукт, оскільки щільність продуктів відрізняється."
    elif result["status"] == "invalid":
        content = "Кількість повинна бути більшою за нуль."
    else:
        content = "У локальній таблиці немає такої конвертації. Не підставляйте приблизне значення з пам'яті."
    return content, artifact


@tool(response_format="content_and_artifact")
def substitution_finder(ingredient: str) -> tuple[str, dict[str, Any]]:
    """Знайди перевірені локальні заміни для названого кулінарного інгредієнта."""
    result = find_substitutions(ingredient)
    artifact = {"kind": "substitution_finder", **result}
    if result["status"] != "ok":
        return f"У локальній базі не знайдено заміни для «{ingredient}».", artifact

    lines = [f"Замінники для «{result['ingredient']}»:"]
    for option in result["options"]:
        lines.append(
            f"- {option['замінник']}. Для: {option['для']}. Примітка: {option['примітка']}."
        )
    return "\n".join(lines), artifact


@tool(args_schema=RecipeRevision, response_format="content_and_artifact")
def recipe_editor(
    reason: str,
    ingredients: list[RecipeIngredientRevision],
    steps: list[str],
) -> tuple[str, dict[str, Any]]:
    """Збережи повну, узгоджену нову версію поточного рецепта.

    Не передавай часткові патчі. Один виклик містить весь підсумковий список
    інгредієнтів та всі кроки приготування після підтвердженої зміни.
    """
    clean_reason = reason.strip()
    artifact = {
        "kind": "recipe_editor",
        "status": "ok",
        "reason": clean_reason,
        "ingredients": [],
        "steps": [],
    }

    if not clean_reason:
        artifact["status"] = "invalid"
        return "Потрібно вказати коротку причину зміни.", artifact
    if not ingredients:
        artifact["status"] = "invalid"
        return "Потрібен повний непорожній список інгредієнтів рецепта.", artifact
    if not steps:
        artifact["status"] = "invalid"
        return "Потрібні всі непорожні кроки приготування рецепта.", artifact

    for ingredient in ingredients:
        clean_name = ingredient.name.strip()
        clean_unit = ingredient.unit.strip() if ingredient.unit else None
        clean_note = ingredient.note.strip() if ingredient.note else None
        quantity = ingredient.quantity
        if not clean_name:
            artifact["status"] = "invalid"
            return "Кожен інгредієнт повинен мати назву.", artifact
        if quantity is not None and quantity <= 0:
            artifact["status"] = "invalid"
            return "Кількість інгредієнта повинна бути більшою за нуль.", artifact
        if quantity is not None and not clean_unit:
            artifact["status"] = "invalid"
            return "Для точної кількості потрібно вказати одиницю.", artifact
        artifact["ingredients"].append(
            {
                "name": clean_name,
                "quantity": quantity,
                "unit": clean_unit,
                "note": clean_note,
            }
        )

    artifact["steps"] = [_clean_step(step) for step in steps]
    if any(not step for step in artifact["steps"]):
        artifact["status"] = "invalid"
        return "Кожен крок приготування повинен містити текст.", artifact

    return "Рецепт оновлено цілісною версією.", artifact


def get_tools() -> list[Any]:
    return [recipe_search, unit_converter, substitution_finder, recipe_editor]
