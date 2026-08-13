from chefbot.services import (
    DataValidationError,
    format_ingredient,
    known_ingredients,
    load_conversions,
    load_recipes,
    load_substitutions,
)


def test_loads_expected_legacy_counts() -> None:
    assert len(load_recipes()) == 20
    assert len(load_conversions()) == 15
    assert len(load_substitutions()) == 12


def test_recipe_ids_are_unique() -> None:
    ids = [recipe["id"] for recipe in load_recipes()]
    assert len(ids) == len(set(ids))


def test_known_ingredients_are_sorted_and_unique() -> None:
    ingredients = known_ingredients()
    assert ingredients == sorted(set(ingredients))
    assert "куряче філе" in ingredients
    assert "картопля" in ingredients


def test_formats_numeric_and_note_ingredients() -> None:
    assert format_ingredient({"name": "олія", "quantity": 2, "unit": "ст.л.", "note": None}) == "олія — 2 ст.л."
    assert format_ingredient({"name": "сіль", "quantity": None, "unit": None, "note": "за смаком"}) == "сіль — за смаком"
