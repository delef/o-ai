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


from chefbot.services import search_recipes


def test_exact_recipe_name_ranks_first() -> None:
    matches = search_recipes("Дай рецепт борщу")
    assert matches[0]["recipe"]["id"] == "borshch"
    assert "назва" in matches[0]["match_reasons"]


def test_ukrainian_ingredient_forms_find_chicken_and_potatoes() -> None:
    matches = search_recipes("Що приготувати з курки та картоплі?")
    assert matches[0]["recipe"]["id"] == "chicken-potatoes"


def test_gluten_free_query_excludes_recipes_with_gluten() -> None:
    matches = search_recipes("Порадь рецепт без глютену")
    assert matches
    assert all(match["recipe"]["gluten_free"] for match in matches)


def test_category_query_returns_tagged_recipe() -> None:
    matches = search_recipes("Хочу швидкий сніданок")
    assert matches
    assert "сніданок" in matches[0]["recipe"]["tags"]
    assert "швидко" in matches[0]["recipe"]["tags"]


def test_unknown_recipe_returns_empty_list() -> None:
    assert search_recipes("фуа-гра з трюфелем") == []
