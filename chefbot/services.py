from __future__ import annotations

import copy
import json
import re
import unicodedata
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


STOP_WORDS = {
    "аби", "або", "без", "будь", "вона", "вони", "для", "дати", "дай",
    "знайди", "можна", "порадь", "потрібен", "потрібна", "приготувати",
    "рецепт", "страва", "страву", "хочу", "щось", "який", "яка",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.casefold())
    normalized = normalized.replace("’", "'").replace("`", "'")
    return " ".join(re.findall(r"[a-zа-яіїєґ0-9']+", normalized))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) > 2 and token not in STOP_WORDS
    }


def _contains_gluten_free_request(query: str) -> bool:
    normalized = normalize_text(query)
    return "без глютену" in normalized or "безглютен" in normalized or "gluten free" in normalized


def search_recipes(query: str, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(query, str) or not query.strip() or limit <= 0:
        return []

    query_normalized = normalize_text(query)
    query_tokens = _tokens(query)
    gluten_free_only = _contains_gluten_free_request(query)
    matches: list[dict[str, Any]] = []

    for index, recipe in enumerate(load_recipes()):
        if gluten_free_only and not recipe["gluten_free"]:
            continue

        score = 0
        reasons: list[str] = []
        name = normalize_text(recipe["name"])

        if query_normalized == name:
            score += 100
            reasons.append("назва")
        elif name in query_normalized or query_normalized in name:
            score += 50
            reasons.append("назва")

        ingredient_hits = []
        for ingredient in recipe["ingredients"]:
            ingredient_name = normalize_text(ingredient["name"])
            if any(token in ingredient_name or ingredient_name in token for token in query_tokens):
                ingredient_hits.append(ingredient["name"])
        if ingredient_hits:
            score += 12 * len(ingredient_hits)
            reasons.append("інгредієнти: " + ", ".join(ingredient_hits))

        tag_hits = []
        for tag in recipe["tags"]:
            tag_normalized = normalize_text(tag)
            if any(token in tag_normalized or tag_normalized in token for token in query_tokens):
                tag_hits.append(tag)
        if tag_hits:
            score += 8 * len(tag_hits)
            reasons.append("теги: " + ", ".join(tag_hits))

        alias_hits = []
        for alias in recipe["aliases"]:
            alias_normalized = normalize_text(alias)
            if alias_normalized in query_normalized or any(token == alias_normalized for token in query_tokens):
                alias_hits.append(alias)
        if alias_hits:
            score += 10 * len(alias_hits)
            reasons.append("форми слів: " + ", ".join(alias_hits))

        if gluten_free_only:
            score += 20
            reasons.append("без глютену")

        if score > 0:
            matches.append(
                {
                    "recipe": copy.deepcopy(recipe),
                    "score": score,
                    "match_reasons": reasons,
                    "source_order": index,
                }
            )

    matches.sort(key=lambda item: (-item["score"], item["source_order"]))
    for match in matches:
        match.pop("source_order", None)
    return matches[:limit]


UNIT_ALIASES = {
    "склянка": "склянка",
    "склянки": "склянка",
    "склянок": "склянка",
    "ст л": "ст.л.",
    "столова ложка": "ст.л.",
    "столові ложки": "ст.л.",
    "столових ложок": "ст.л.",
    "ч л": "ч.л.",
    "чайна ложка": "ч.л.",
    "чайні ложки": "ч.л.",
    "чайних ложок": "ч.л.",
    "г": "г",
    "грам": "г",
    "грами": "г",
    "грамів": "г",
    "мл": "мл",
    "мілілітр": "мл",
    "мілілітри": "мл",
    "мілілітрів": "мл",
}


def normalize_unit(value: str) -> str:
    normalized = normalize_text(value).replace(".", "")
    return UNIT_ALIASES.get(normalized, normalized)


def _rounded(value: float) -> int | float:
    rounded = round(value, 2)
    return int(rounded) if rounded.is_integer() else rounded


def convert_units(
    amount: float,
    from_unit: str,
    to_unit: str,
    product: str | None = None,
) -> dict[str, Any]:
    if not isinstance(amount, (int, float)) or amount <= 0:
        return {"status": "invalid", "reason": "amount_must_be_positive"}

    source = normalize_unit(from_unit)
    target = normalize_unit(to_unit)
    product_normalized = normalize_text(product or "") or None

    if source == target:
        return {
            "status": "ok",
            "amount": amount,
            "from_unit": source,
            "to_unit": target,
            "product": product_normalized,
            "result": _rounded(float(amount)),
            "approximate": False,
        }

    direct = [
        item
        for item in load_conversions()
        if normalize_unit(item["from_unit"]) == source and normalize_unit(item["to_unit"]) == target
    ]
    inverse = [
        item
        for item in load_conversions()
        if normalize_unit(item["from_unit"]) == target and normalize_unit(item["to_unit"]) == source
    ]

    candidates = direct or inverse
    product_specific = [item for item in candidates if item["product"] is not None]
    generic = [item for item in candidates if item["product"] is None]

    selected = None
    if product_normalized:
        selected = next(
            (item for item in product_specific if normalize_text(item["product"]) == product_normalized),
            None,
        )
    if selected is None and generic:
        selected = generic[0]
    if selected is None and product_specific and not product_normalized:
        return {"status": "clarification", "reason": "product_required"}
    if selected is None:
        return {
            "status": "not_found",
            "amount": amount,
            "from_unit": source,
            "to_unit": target,
            "product": product_normalized,
        }

    if direct:
        result = float(amount) * float(selected["factor"])
    else:
        result = float(amount) / float(selected["factor"])

    return {
        "status": "ok",
        "amount": amount,
        "from_unit": source,
        "to_unit": target,
        "product": product_normalized,
        "result": _rounded(result),
        "approximate": True,
    }


def find_substitutions(ingredient: str) -> dict[str, Any]:
    normalized = normalize_text(ingredient)
    for key, options in load_substitutions().items():
        key_normalized = normalize_text(key)
        if key_normalized in normalized or normalized in key_normalized:
            return {
                "status": "ok",
                "ingredient": key,
                "options": copy.deepcopy(options),
            }
    return {"status": "not_found", "ingredient": normalized, "options": []}
