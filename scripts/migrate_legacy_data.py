from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Final_ChefBot_ipynb__.ipynb"
DATA_DIR = ROOT / "data"

RECIPE_IDS = {
    "борщ": "borshch",
    "омлет": "omelet",
    "курка з картоплею": "chicken-potatoes",
    "вареники з картоплею": "potato-dumplings",
    "млинці": "crepes",
    "овочевий салат": "vegetable-salad",
    "рибний суп": "fish-soup",
    "овочеве рагу": "vegetable-stew",
    "яблучний пиріг": "apple-pie",
    "рисова каша": "rice-porridge",
    "гречка з куркою": "buckwheat-chicken",
    "салат з тунцем": "tuna-salad",
    "паста з куркою у вершковому соусі": "creamy-chicken-pasta",
    "запечений лосось з овочами": "baked-salmon-vegetables",
    "рис з куркою та овочами": "rice-chicken-vegetables",
    "шакшука": "shakshuka",
    "крем-суп з кабачка": "zucchini-cream-soup",
    "спагеті з томатним соусом": "spaghetti-tomato-sauce",
    "запечені овочі з фетою": "baked-vegetables-feta",
    "бананові панкейки": "banana-pancakes",
}

RECIPE_ALIASES = {
    "борщ": ["борщу", "борщем"],
    "омлет": ["омлету", "яйця"],
    "курка з картоплею": ["курка", "курки", "куркою", "куряче", "курятина", "картопля", "картоплі"],
    "вареники з картоплею": ["вареники", "вареників", "картопля", "картоплі"],
    "млинці": ["млинець", "млинців"],
    "овочевий салат": ["овочі", "овочів", "салат"],
    "рибний суп": ["риба", "риби", "рибою", "суп"],
    "овочеве рагу": ["овочі", "овочів", "рагу"],
    "яблучний пиріг": ["яблука", "яблук", "пиріг"],
    "рисова каша": ["рис", "рису", "каша"],
    "гречка з куркою": ["гречка", "гречки", "курка", "курки", "куркою"],
    "салат з тунцем": ["тунець", "тунця", "тунцем", "салат"],
    "паста з куркою у вершковому соусі": ["паста", "курка", "курки", "вершки", "вершковий"],
    "запечений лосось з овочами": ["лосось", "лосося", "овочі", "овочів"],
    "рис з куркою та овочами": ["рис", "рису", "курка", "курки", "овочі", "овочів"],
    "шакшука": ["шакшуку", "яйця", "помідори"],
    "крем-суп з кабачка": ["кабачок", "кабачка", "кабачки", "крем суп"],
    "спагеті з томатним соусом": ["спагеті", "паста", "томати", "помідори"],
    "запечені овочі з фетою": ["овочі", "овочів", "фета", "фетою"],
    "бананові панкейки": ["банан", "банани", "панкейк", "панкейки"],
}


def extract_assignments() -> dict[str, Any]:
    notebook = json.loads(SOURCE.read_text(encoding="utf-8"))
    source = "".join(notebook["cells"][5]["source"])
    tree = ast.parse(source)
    wanted = {"RECIPES_DB", "UNIT_CONVERSIONS", "SUBSTITUTIONS"}
    values: dict[str, Any] = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in wanted:
            values[target.id] = ast.literal_eval(node.value)

    missing = wanted.difference(values)
    if missing:
        raise ValueError(f"Legacy notebook is missing: {sorted(missing)}")
    return values


def parse_ingredient(raw: str) -> dict[str, Any]:
    name, value = [part.strip() for part in raw.split("—", 1)]
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s+(.+)", value)
    if not match:
        return {"name": name, "quantity": None, "unit": None, "note": value}

    quantity = float(match.group(1).replace(",", "."))
    return {
        "name": name,
        "quantity": int(quantity) if quantity.is_integer() else quantity,
        "unit": match.group(2).strip(),
        "note": None,
    }


def parse_steps(value: str) -> list[str]:
    chunks = re.split(r"\s*(?=\d+\.\s)", value.strip())
    return [re.sub(r"^\d+\.\s*", "", chunk).strip() for chunk in chunks if chunk.strip()]


def build_recipes(raw: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    recipes: list[dict[str, Any]] = []
    for name, recipe in raw.items():
        recipes.append(
            {
                "id": RECIPE_IDS[name],
                "name": name,
                "aliases": RECIPE_ALIASES[name],
                "ingredients": [parse_ingredient(item) for item in recipe["ingredients"]],
                "time_minutes": recipe["time_minutes"],
                "servings": recipe["servings"],
                "steps": parse_steps(recipe["instructions"]),
                "tags": recipe["tags"],
                "gluten_free": recipe["gluten_free"],
            }
        )
    return recipes


def build_conversions(raw: dict[tuple[str, str, str], float]) -> list[dict[str, Any]]:
    return [
        {
            "from_unit": from_unit,
            "to_unit": to_unit,
            "product": product or None,
            "factor": float(factor),
        }
        for (from_unit, to_unit, product), factor in raw.items()
    ]


def write_json(name: str, value: Any) -> None:
    path = DATA_DIR / name
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    values = extract_assignments()
    DATA_DIR.mkdir(exist_ok=True)
    write_json("recipes.json", build_recipes(values["RECIPES_DB"]))
    write_json("conversions.json", build_conversions(values["UNIT_CONVERSIONS"]))
    write_json("substitutions.json", values["SUBSTITUTIONS"])


if __name__ == "__main__":
    main()
