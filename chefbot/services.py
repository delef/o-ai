from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


class DataValidationError(ValueError):
    """Raised when committed ChefBot data violates its runtime contract."""


def _read_json(name: str) -> Any:
    path = DATA_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"Не вдалося завантажити {name}: {exc}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DataValidationError(message)


def _validate_ingredient(value: Any, recipe_id: str) -> None:
    _require(isinstance(value, dict), f"{recipe_id}: ingredient must be an object")
    _require(isinstance(value.get("name"), str) and value["name"].strip() != "", f"{recipe_id}: ingredient name is required")
    quantity = value.get("quantity")
    _require(quantity is None or isinstance(quantity, (int, float)), f"{recipe_id}: invalid ingredient quantity")
    _require(value.get("unit") is None or isinstance(value.get("unit"), str), f"{recipe_id}: invalid ingredient unit")
    _require(value.get("note") is None or isinstance(value.get("note"), str), f"{recipe_id}: invalid ingredient note")


@lru_cache(maxsize=1)
def load_recipes() -> tuple[dict[str, Any], ...]:
    value = _read_json("recipes.json")
    _require(isinstance(value, list) and value, "recipes.json must contain a non-empty list")
    ids: set[str] = set()
    required = {"id", "name", "aliases", "ingredients", "time_minutes", "servings", "steps", "tags", "gluten_free"}

    for recipe in value:
        _require(isinstance(recipe, dict), "Every recipe must be an object")
        _require(required.issubset(recipe), f"Recipe is missing fields: {sorted(required.difference(recipe))}")
        recipe_id = recipe["id"]
        _require(isinstance(recipe_id, str) and recipe_id != "", "Recipe id is required")
        _require(recipe_id not in ids, f"Duplicate recipe id: {recipe_id}")
        ids.add(recipe_id)
        _require(isinstance(recipe["name"], str) and recipe["name"].strip() != "", f"{recipe_id}: name is required")
        _require(
            isinstance(recipe["aliases"], list)
            and all(isinstance(alias, str) and alias.strip() for alias in recipe["aliases"]),
            f"{recipe_id}: aliases must contain non-empty text",
        )
        _require(isinstance(recipe["ingredients"], list) and recipe["ingredients"], f"{recipe_id}: ingredients are required")
        for ingredient in recipe["ingredients"]:
            _validate_ingredient(ingredient, recipe_id)
        _require(isinstance(recipe["time_minutes"], int) and recipe["time_minutes"] > 0, f"{recipe_id}: invalid time")
        _require(isinstance(recipe["servings"], int) and recipe["servings"] > 0, f"{recipe_id}: invalid servings")
        _require(
            isinstance(recipe["steps"], list)
            and recipe["steps"]
            and all(isinstance(step, str) and step.strip() for step in recipe["steps"]),
            f"{recipe_id}: steps must contain non-empty text",
        )
        _require(
            isinstance(recipe["tags"], list)
            and all(isinstance(tag, str) and tag.strip() for tag in recipe["tags"]),
            f"{recipe_id}: tags must contain non-empty text",
        )
        _require(isinstance(recipe["gluten_free"], bool), f"{recipe_id}: gluten_free must be boolean")

    return tuple(value)


@lru_cache(maxsize=1)
def load_conversions() -> tuple[dict[str, Any], ...]:
    value = _read_json("conversions.json")
    _require(isinstance(value, list) and value, "conversions.json must contain a non-empty list")
    for item in value:
        _require(isinstance(item, dict), "Every conversion must be an object")
        _require(isinstance(item.get("from_unit"), str), "Conversion from_unit is required")
        _require(isinstance(item.get("to_unit"), str), "Conversion to_unit is required")
        _require(item.get("product") is None or isinstance(item.get("product"), str), "Conversion product must be text or null")
        _require(isinstance(item.get("factor"), (int, float)) and item["factor"] > 0, "Conversion factor must be positive")
    return tuple(value)


@lru_cache(maxsize=1)
def load_substitutions() -> dict[str, list[dict[str, str]]]:
    value = _read_json("substitutions.json")
    _require(isinstance(value, dict) and value, "substitutions.json must contain a non-empty object")
    for ingredient, options in value.items():
        _require(isinstance(ingredient, str) and ingredient.strip() != "", "Substitution key is required")
        _require(isinstance(options, list) and options, f"{ingredient}: substitution options are required")
        for option in options:
            _require(isinstance(option, dict), f"{ingredient}: substitution must be an object")
            _require({"замінник", "для", "примітка"}.issubset(option), f"{ingredient}: substitution fields are incomplete")
            _require(
                all(isinstance(option[field], str) and option[field].strip() for field in ("замінник", "для", "примітка")),
                f"{ingredient}: substitution values must contain non-empty text",
            )
    return value


def known_ingredients() -> list[str]:
    return sorted({ingredient["name"] for recipe in load_recipes() for ingredient in recipe["ingredients"]})


def _format_quantity(value: int | float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:g}"
    return str(int(value))


def format_ingredient(ingredient: dict[str, Any]) -> str:
    if ingredient.get("quantity") is None:
        value = ingredient.get("note") or "кількість не вказана"
    else:
        value = f"{_format_quantity(ingredient['quantity'])} {ingredient['unit']}"
    return f"{ingredient['name']} — {value}"
