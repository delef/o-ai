from __future__ import annotations

from typing import Any

from langchain.tools import tool

from chefbot.services import (
    convert_units,
    find_substitutions,
    format_ingredient,
    search_recipes,
)


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


def get_tools() -> list[Any]:
    return [recipe_search, unit_converter, substitution_finder]
