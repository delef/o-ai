from __future__ import annotations

from typing import Any, Literal

from langchain.tools import tool

from chefbot.services import (
    convert_units,
    find_substitutions,
    format_ingredient,
    search_recipes,
)


RECIPE_EDIT_ACTIONS = {"add", "replace", "remove", "update_step"}


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


@tool(response_format="content_and_artifact", parse_docstring=True)
def recipe_editor(
    action: Literal["add", "replace", "remove", "update_step"],
    reason: str,
    ingredient: str = "",
    replacement: str = "",
    quantity: float = 0,
    unit: str = "",
    note: str = "",
    step_number: int = 0,
    step_text: str = "",
) -> tuple[str, dict[str, Any]]:
    """Зафіксуй підтверджену зміну поточного рецепта.

    Args:
        action: Використай add, replace або remove для інгредієнта; update_step, коли змінюється лише крок.
        reason: Коротка видима причина на основі явного запиту користувача, без вигаданої користі.
        ingredient: Точна назва нового або наявного інгредієнта; порожня для update_step.
        replacement: Нова назва інгредієнта, обов'язкова лише для replace.
        quantity: Точна кількість лише з явних даних; 0 означає, що її не вказано.
        unit: Одиниця для quantity; порожня, коли кількість не вказана.
        note: Коротка явна примітка до інгредієнта, наприклад «за смаком».
        step_number: 1-based номер обов'язкового кроку для зміни інгредієнта або окремого оновлення.
        step_text: Повний новий текст кроку, обов'язковий для зміни інгредієнта або кроку.
    """
    normalized_action = action.strip().casefold()
    clean_ingredient = ingredient.strip()
    clean_replacement = replacement.strip()
    clean_reason = reason.strip()
    clean_step = step_text.strip()
    artifact = {
        "kind": "recipe_editor",
        "status": "ok",
        "action": normalized_action,
        "ingredient": clean_ingredient,
        "replacement": clean_replacement,
        "quantity": quantity if quantity > 0 else None,
        "unit": unit.strip() or None,
        "note": note.strip() or None,
        "step_number": step_number,
        "step_text": clean_step,
        "reason": clean_reason,
    }

    invalid_reason = ""
    if normalized_action not in RECIPE_EDIT_ACTIONS:
        invalid_reason = "Непідтримувана дія для рецепта."
    elif not clean_reason:
        invalid_reason = "Потрібно вказати коротку причину зміни."
    elif normalized_action in {"add", "replace", "remove"} and not clean_ingredient:
        invalid_reason = "Потрібно вказати інгредієнт."
    elif normalized_action == "replace" and not clean_replacement:
        invalid_reason = "Для заміни потрібно вказати новий інгредієнт."
    elif quantity < 0:
        invalid_reason = "Кількість не може бути від'ємною."
    elif quantity > 0 and not artifact["unit"]:
        invalid_reason = "Для точної кількості потрібно вказати одиницю."
    elif (step_number > 0) != bool(clean_step):
        invalid_reason = "Номер і новий текст кроку потрібно передати разом."
    elif normalized_action in {"add", "replace", "remove"} and step_number <= 0:
        invalid_reason = (
            "Зміна інгредієнта має містити оновлений крок приготування, "
            "щоб рецепт залишався цілісним."
        )
    elif normalized_action == "update_step" and step_number <= 0:
        invalid_reason = "Для зміни приготування потрібно вказати крок."

    if invalid_reason:
        artifact["status"] = "invalid"
        return invalid_reason, artifact

    if normalized_action == "add":
        content = f"До рецепта додано «{clean_ingredient}»."
    elif normalized_action == "replace":
        content = f"У рецепті «{clean_ingredient}» замінено на «{clean_replacement}»."
    elif normalized_action == "remove":
        content = f"З рецепта видалено «{clean_ingredient}»."
    else:
        content = f"Оновлено крок {step_number} рецепта."
    return content, artifact


def get_tools() -> list[Any]:
    return [recipe_search, unit_converter, substitution_finder, recipe_editor]
