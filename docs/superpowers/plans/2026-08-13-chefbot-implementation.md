# ChefBot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, modular ChefBot project with a thin Colab notebook, three grounded tools, evidence-producing evaluation, and the approved ingredient-first Streamlit frontend.

**Architecture:** JSON files are the only runtime data source. Pure Python services perform deterministic lookup and conversion; LangChain tools wrap those services and return both model-facing text and application-facing artifacts. Colab, evaluation, and Streamlit all call the same agent factory and result parser, so tool routing, usage metadata, and displayed recipe facts stay consistent.

**Tech Stack:** Python 3.11, LangChain 1.3.11, langchain-openai 1.3.3, OpenAI `gpt-4o-mini`, Streamlit 1.60.0, pytest, nbformat, GitHub Actions.

---

## File responsibility map

| Path | Responsibility |
|---|---|
| `Final_ChefBot_ipynb__.ipynb` | Immutable legacy source until parity is proven; removed from the final tree only after it is committed in history. |
| `Final_ChefBot.ipynb` | Thin, non-blocking Colab walkthrough and required final notebook artifact. |
| `scripts/migrate_legacy_data.py` | Temporary, reproducible conversion of the legacy Python literals into normalized JSON; removed with the legacy source after parity. |
| `scripts/build_notebook.py` | Deterministic generator for the final notebook. |
| `chefbot/services.py` | Data loading, validation, normalization, recipe search, conversion, substitution lookup, and display formatting. |
| `chefbot/tools.py` | Three LangChain tool wrappers with `(content, artifact)` responses. |
| `chefbot/prompt.py` | Single ChefBot system prompt and behavioral boundaries. |
| `chefbot/agent.py` | Agent factory, safe tool-error middleware, tool-event extraction, token aggregation, and run result. |
| `chefbot/evaluation.py` | Scenario execution, routing assertions, latency/token/cost calculation, CSV writer, and CLI. |
| `data/*.json` | Single source of truth for 20 recipes, 15 conversions, and 12 substitution groups. |
| `evaluation/scenarios.json` | Versioned live-agent test cases and expected behavior. |
| `evaluation/results.csv` | Latest real evaluation evidence; generated only by a run with an API key. |
| `app.py` | Approved ingredient-first Streamlit UI; no duplicated data or agent logic. |
| `tests/` | API-free deterministic, tool-contract, agent-parser, evaluation, notebook, and UI smoke tests. |
| `.streamlit/config.toml` | Stable theme values matching the approved mockup. |
| `.github/workflows/tests.yml` | Clean Python 3.11 unit-test run on pushes and pull requests. |
| `README.md` | Product boundary, architecture, Colab button, setup, tests, evaluation, and frontend instructions. |

Verified API contracts for this plan:

- LangChain tools support `response_format="content_and_artifact"` and convert the returned two-tuple into `ToolMessage.content` plus `ToolMessage.artifact`: [LangChain reference](https://reference.langchain.com/python/langchain-core/tools/convert/tool).
- `ChatOpenAI` exposes standardized `tool_calls` and `usage_metadata`: [LangChain OpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai).
- Streamlit `st.multiselect` supports `accept_new_options=True`, which supplies the editable ingredient-chip interaction without a third-party component: [Streamlit reference](https://docs.streamlit.io/develop/api-reference/widgets/st.multiselect).
- The dated cost constants use the standard `gpt-4o-mini` token rates shown on the [official OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4o-mini).

## Task 1: Preserve the legacy source and establish dependencies

**Files:**
- Track: `Final_ChefBot_ipynb__.ipynb`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`

- [ ] **Step 1: Recheck that the legacy notebook contains no credential literal**

Run:

```bash
rg -n -e 'sk-[A-Za-z0-9_-]{16,}' -e 'gh[pousr]_[A-Za-z0-9]{20,}' -e 'AIza[0-9A-Za-z_-]{20,}' Final_ChefBot_ipynb__.ipynb
```

Expected: no output and exit status `1`. References such as `OPENAI_API_KEY` are allowed; actual key values are not.

- [ ] **Step 2: Commit the unchanged legacy notebook so later cleanup is recoverable**

```bash
git add Final_ChefBot_ipynb__.ipynb
git commit -m "chore: preserve legacy ChefBot notebook"
```

Expected: one commit containing only the original notebook.

- [ ] **Step 3: Add runtime dependencies**

Create `requirements.txt`:

```text
langchain==1.3.11
langchain-openai==1.3.3
streamlit==1.60.0
```

Create `requirements-dev.txt`:

```text
-r requirements.txt
nbformat==5.10.4
pytest==8.4.2
```

- [ ] **Step 4: Add secret and generated-file exclusions**

Create `.gitignore`:

```gitignore
.DS_Store
.env
.env.*
!.env.example
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.streamlit/secrets.toml
.superpowers/
evaluation/results.local.csv
```

- [ ] **Step 5: Install and confirm the pinned packages**

Run:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -c "import langchain, langchain_openai, streamlit; print(langchain.__version__, streamlit.__version__)"
```

Expected: installation succeeds and prints `1.3.11 1.60.0` with no import error.

- [ ] **Step 6: Commit the scaffold**

```bash
git add requirements.txt requirements-dev.txt .gitignore
git commit -m "build: pin ChefBot dependencies"
```

## Task 2: Migrate the notebook data into normalized JSON

**Files:**
- Create: `scripts/migrate_legacy_data.py`
- Create: `data/recipes.json`
- Create: `data/conversions.json`
- Create: `data/substitutions.json`

- [ ] **Step 1: Add the deterministic migration script**

Create `scripts/migrate_legacy_data.py`:

```python
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
```

- [ ] **Step 2: Generate the JSON files**

Run:

```bash
python3 scripts/migrate_legacy_data.py
python3 -c "import json; from pathlib import Path; p=Path('data'); print(len(json.load(open(p/'recipes.json'))), len(json.load(open(p/'conversions.json'))), len(json.load(open(p/'substitutions.json'))))"
```

Expected: `20 15 12`.

- [ ] **Step 3: Confirm the generated data is stable**

Record hashes, regenerate, and confirm that all three hashes remain identical:

```bash
shasum data/recipes.json data/conversions.json data/substitutions.json
python3 scripts/migrate_legacy_data.py
shasum data/recipes.json data/conversions.json data/substitutions.json
```

Expected: the two groups of three SHA-1 hashes are identical.

- [ ] **Step 4: Commit the migration and generated data**

```bash
git add scripts/migrate_legacy_data.py data/recipes.json data/conversions.json data/substitutions.json
git commit -m "data: extract ChefBot knowledge bases"
```

## Task 3: Add validated data loading and display formatting

**Files:**
- Create: `chefbot/__init__.py`
- Create: `chefbot/services.py`
- Create: `tests/test_services.py`

- [ ] **Step 1: Write failing loader and formatting tests**

Create `tests/test_services.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_services.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'chefbot'`.

- [ ] **Step 3: Implement validated loaders and formatting**

Create `chefbot/__init__.py`:

```python
"""ChefBot package."""
```

Create `chefbot/services.py`:

```python
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
```

- [ ] **Step 4: Run the loader tests**

Run:

```bash
python3 -m pytest tests/test_services.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Commit the validated data boundary**

```bash
git add chefbot/__init__.py chefbot/services.py tests/test_services.py
git commit -m "feat: validate ChefBot data sources"
```

## Task 4: Implement deterministic recipe search

**Files:**
- Modify: `chefbot/services.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: Add failing recipe-search tests**

Append to `tests/test_services.py`:

```python
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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_services.py -k 'recipe or gluten or category or unknown' -v
```

Expected: collection fails because `search_recipes` does not exist.

- [ ] **Step 3: Add normalization and deterministic ranking**

Add these imports to `chefbot/services.py`:

```python
import copy
import re
import unicodedata
```

Append to `chefbot/services.py`:

```python
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
```

- [ ] **Step 4: Run all service tests**

Run:

```bash
python3 -m pytest tests/test_services.py -v
```

Expected: `9 passed`.

- [ ] **Step 5: Commit recipe search**

```bash
git add chefbot/services.py tests/test_services.py
git commit -m "feat: add grounded recipe search"
```

## Task 5: Implement unit conversion and substitution lookup

**Files:**
- Modify: `chefbot/services.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: Add failing conversion and substitution tests**

Append to `tests/test_services.py`:

```python
from chefbot.services import convert_units, find_substitutions


def test_direct_product_conversion() -> None:
    result = convert_units(2, "склянки", "грами", "борошно")
    assert result["status"] == "ok"
    assert result["result"] == 300
    assert result["to_unit"] == "г"


def test_inverse_product_conversion() -> None:
    result = convert_units(300, "г", "склянки", "борошно")
    assert result["status"] == "ok"
    assert result["result"] == 2


def test_conversion_requires_product_when_density_matters() -> None:
    result = convert_units(1, "склянка", "г")
    assert result["status"] == "clarification"
    assert result["reason"] == "product_required"


def test_unsupported_conversion_is_explicit() -> None:
    result = convert_units(3, "літр", "кг", "олія")
    assert result["status"] == "not_found"


def test_non_positive_amount_is_invalid() -> None:
    result = convert_units(0, "склянка", "мл")
    assert result["status"] == "invalid"


def test_known_substitution_returns_grounded_options() -> None:
    result = find_substitutions("Чим замінити яйця у випічці?")
    assert result["status"] == "ok"
    assert result["ingredient"] == "яйця"
    assert result["options"]


def test_unknown_substitution_is_explicit() -> None:
    result = find_substitutions("трюфельна паста")
    assert result == {"status": "not_found", "ingredient": "трюфельна паста", "options": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_services.py -k 'conversion or substitution or amount' -v
```

Expected: collection fails because `convert_units` and `find_substitutions` do not exist.

- [ ] **Step 3: Add unit aliases and bidirectional conversion**

Append to `chefbot/services.py`:

```python
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
```

- [ ] **Step 4: Run all service tests**

Run:

```bash
python3 -m pytest tests/test_services.py -v
```

Expected: `16 passed`.

- [ ] **Step 5: Commit deterministic conversions and substitutions**

```bash
git add chefbot/services.py tests/test_services.py
git commit -m "feat: add culinary conversion and substitutions"
```

## Task 6: Wrap deterministic services as LangChain tools

**Files:**
- Create: `chefbot/tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tool-contract tests**

Create `tests/test_tools.py`:

```python
from langchain.messages import ToolMessage

from chefbot.tools import recipe_search, substitution_finder, unit_converter


def invoke(tool, call_id: str, **args):
    return tool.invoke(
        {
            "name": tool.name,
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }
    )


def test_recipe_tool_returns_content_and_artifact() -> None:
    message = invoke(recipe_search, "recipe-1", query="курки та картоплі")
    assert isinstance(message, ToolMessage)
    assert message.name == "recipe_search"
    assert message.artifact["kind"] == "recipe_search"
    assert message.artifact["status"] == "ok"
    assert message.artifact["matches"][0]["recipe"]["id"] == "chicken-potatoes"


def test_conversion_tool_exposes_structured_result() -> None:
    message = invoke(
        unit_converter,
        "conversion-1",
        amount=2,
        from_unit="склянки",
        to_unit="грами",
        product="борошно",
    )
    assert message.artifact["kind"] == "unit_converter"
    assert message.artifact["status"] == "ok"
    assert message.artifact["result"] == 300


def test_substitution_tool_reports_missing_data_without_invention() -> None:
    message = invoke(substitution_finder, "substitution-1", ingredient="трюфельна паста")
    assert message.artifact == {
        "kind": "substitution_finder",
        "status": "not_found",
        "ingredient": "трюфельна паста",
        "options": [],
    }
    assert "не знайдено" in message.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_tools.py -v
```

Expected: collection fails because `chefbot.tools` does not exist.

- [ ] **Step 3: Implement the three artifact-producing tools**

Create `chefbot/tools.py`:

```python
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
```

- [ ] **Step 4: Run tool and service tests**

Run:

```bash
python3 -m pytest tests/test_services.py tests/test_tools.py -v
```

Expected: `19 passed`.

- [ ] **Step 5: Commit tool contracts**

```bash
git add chefbot/tools.py tests/test_tools.py
git commit -m "feat: expose grounded ChefBot tools"
```

## Task 7: Create the prompt, agent factory, and observable run result

**Files:**
- Create: `chefbot/prompt.py`
- Create: `chefbot/agent.py`
- Create: `tests/test_agent.py`
- Modify: `chefbot/__init__.py`

- [ ] **Step 1: Write failing agent-parser tests**

Create `tests/test_agent.py`:

```python
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from chefbot.agent import MissingAPIKeyError, create_chefbot, run_chefbot


class FakeAgent:
    def invoke(self, state):
        prior = list(state["messages"])
        return {
            "messages": [
                *prior,
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recipe_search",
                            "args": {"query": "борщ"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                    usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
                ),
                ToolMessage(
                    content="Борщ",
                    tool_call_id="call-1",
                    name="recipe_search",
                    artifact={"kind": "recipe_search", "status": "ok", "matches": []},
                ),
                AIMessage(
                    content="Ось рецепт борщу.",
                    usage_metadata={"input_tokens": 120, "output_tokens": 20, "total_tokens": 140},
                ),
            ]
        }


def test_missing_key_fails_before_model_creation(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        create_chefbot(api_key=None)
    except MissingAPIKeyError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected MissingAPIKeyError")


def test_run_extracts_answer_tool_artifact_and_usage() -> None:
    result = run_chefbot(FakeAgent(), [HumanMessage(content="Дай рецепт борщу")])
    assert result.answer == "Ось рецепт борщу."
    assert result.tool_events[0].name == "recipe_search"
    assert result.tool_events[0].artifact["status"] == "ok"
    assert result.usage.input_tokens == 220
    assert result.usage.output_tokens == 30
    assert result.usage.total_tokens == 250
    assert result.latency_ms >= 0


def test_run_does_not_count_usage_from_prior_history() -> None:
    prior = AIMessage(
        content="Стара відповідь",
        usage_metadata={"input_tokens": 999, "output_tokens": 999, "total_tokens": 1998},
    )
    result = run_chefbot(FakeAgent(), [HumanMessage(content="Продовжуй"), prior])
    assert result.usage.total_tokens == 250
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_agent.py -v
```

Expected: collection fails because `chefbot.agent` does not exist.

- [ ] **Step 3: Add the single system prompt**

Create `chefbot/prompt.py`:

```python
SYSTEM_PROMPT = """
Ти — ChefBot, дружній персональний кулінарний AI-асистент.

Твоя сфера:
- пошук рецептів у локальній базі;
- вибір страви з наявних продуктів;
- підтримувані кулінарні конвертації;
- підтримувані заміни інгредієнтів;
- короткі загальні пояснення про приготування їжі.

Відповідай українською, якщо користувач не попросив іншу мову. Пиши просто,
доброзичливо і конкретно.

ОБОВ'ЯЗКОВЕ ВИКОРИСТАННЯ ІНСТРУМЕНТІВ:
1. Використовуй recipe_search для рецепта, страви з продуктів, категорії,
   сніданку/обіду/вечері або запиту без глютену.
2. Використовуй unit_converter для будь-якого переведення кулінарних одиниць.
3. Використовуй substitution_finder, коли користувач питає, чим замінити продукт.
4. Комбінований запит може потребувати кількох інструментів.

Не замінюй результат інструмента власними точними значеннями. Якщо інструмент
повернув not_found, чесно скажи, що даних немає, і не вигадуй рецепт,
конвертацію, кількість або заміну. Якщо даних недостатньо, постав одне коротке
уточнювальне запитання.

Враховуй попередні повідомлення поточної розмови. Якщо користувач пише
«чим це замінити?» після рецепта, визнач продукт із контексту лише коли це
однозначно; інакше уточни.

Безпека:
- не став медичних діагнозів і не створюй лікувальних дієт;
- при серйозній алергії не гарантуй безпечність; порадь перевірити склад,
  маркування та умови виробництва конкретного продукту;
- не показуй приховані міркування або chain-of-thought;
- якщо запит не стосується їжі чи приготування, коротко поясни спеціалізацію
  ChefBot і не відповідай як універсальний асистент.

Для знайденого рецепта використовуй тільки назву, інгредієнти, час, порції та
кроки, які повернув recipe_search. Не додавай калорійність, складність, ціну,
рейтинг або інші відсутні поля.
""".strip()
```

- [ ] **Step 4: Implement the agent factory, safe middleware, and telemetry extraction**

Create `chefbot/agent.py`:

```python
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import AIMessage, BaseMessage, ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langchain_openai import ChatOpenAI

from chefbot.prompt import SYSTEM_PROMPT
from chefbot.tools import get_tools


DEFAULT_MODEL = "gpt-4o-mini"


class MissingAPIKeyError(RuntimeError):
    """Raised when a live ChefBot agent is requested without a key."""


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )


@dataclass(frozen=True)
class ToolEvent:
    name: str
    status: str
    content: str
    artifact: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChefBotResult:
    messages: list[BaseMessage]
    answer: str
    tool_events: list[ToolEvent]
    usage: TokenUsage
    latency_ms: int


@wrap_tool_call
def safe_tool_errors(request: ToolCallRequest, handler):
    try:
        return handler(request)
    except Exception:
        return ToolMessage(
            content="Інструмент тимчасово не виконав запит. Спробуйте ще раз або уточніть дані.",
            tool_call_id=request.tool_call["id"],
            name=request.tool_call["name"],
            artifact={
                "kind": request.tool_call["name"],
                "status": "error",
            },
        )


def create_chefbot(
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 700,
):
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "OPENAI_API_KEY не налаштовано. Додайте ключ у Colab Secrets або змінні середовища."
        )

    model = ChatOpenAI(
        api_key=key,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=30,
        max_retries=2,
        stream_usage=True,
    )
    return create_agent(
        model=model,
        tools=get_tools(),
        system_prompt=SYSTEM_PROMPT,
        middleware=[safe_tool_errors],
    )


def _message_text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        return "\n".join(
            block.get("text", "")
            for block in message.content
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}
        ).strip()
    return str(message.content)


def _usage_from_message(message: BaseMessage) -> TokenUsage:
    metadata = getattr(message, "usage_metadata", None) or {}
    details = metadata.get("input_token_details") or {}
    return TokenUsage(
        input_tokens=int(metadata.get("input_tokens", 0)),
        output_tokens=int(metadata.get("output_tokens", 0)),
        total_tokens=int(metadata.get("total_tokens", 0)),
        cached_input_tokens=int(details.get("cache_read", 0)),
    )


def _events(messages: Iterable[BaseMessage]) -> list[ToolEvent]:
    events = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        artifact = message.artifact if isinstance(message.artifact, dict) else {}
        events.append(
            ToolEvent(
                name=message.name or str(artifact.get("kind", "unknown")),
                status=str(artifact.get("status", "unknown")),
                content=_message_text(message),
                artifact=artifact,
            )
        )
    return events


def run_chefbot(agent, messages: list[BaseMessage | dict[str, Any]]) -> ChefBotResult:
    started = time.perf_counter()
    state = agent.invoke({"messages": messages})
    all_messages = list(state["messages"])
    generated = all_messages[len(messages):]
    answer = next(
        (_message_text(message) for message in reversed(generated) if isinstance(message, AIMessage) and _message_text(message)),
        "",
    )
    usage = TokenUsage()
    for message in generated:
        if isinstance(message, AIMessage):
            usage = usage + _usage_from_message(message)

    return ChefBotResult(
        messages=all_messages,
        answer=answer,
        tool_events=_events(generated),
        usage=usage,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )
```

- [ ] **Step 5: Export the stable public API**

Replace `chefbot/__init__.py` with:

```python
"""Public ChefBot API used by Colab and Streamlit."""

from chefbot.agent import (
    ChefBotResult,
    MissingAPIKeyError,
    ToolEvent,
    TokenUsage,
    create_chefbot,
    run_chefbot,
)

__all__ = [
    "ChefBotResult",
    "MissingAPIKeyError",
    "ToolEvent",
    "TokenUsage",
    "create_chefbot",
    "run_chefbot",
]
```

- [ ] **Step 6: Run the complete API-free test suite**

Run:

```bash
python3 -m pytest tests/test_services.py tests/test_tools.py tests/test_agent.py -v
```

Expected: all tests pass without `OPENAI_API_KEY`.

- [ ] **Step 7: Commit the observable agent runtime**

```bash
git add chefbot/prompt.py chefbot/agent.py chefbot/__init__.py tests/test_agent.py
git commit -m "feat: add observable ChefBot agent runtime"
```

## Task 8: Add evidence-producing live evaluation

**Files:**
- Create: `evaluation/scenarios.json`
- Create: `chefbot/evaluation.py`
- Create: `tests/test_evaluation.py`
- Generate after a live run: `evaluation/results.csv`

- [ ] **Step 1: Add the versioned scenario set**

Create `evaluation/scenarios.json`:

```json
[
  {
    "id": "recipe_exact",
    "turns": ["Дай рецепт борщу."],
    "expected_tools": ["recipe_search"],
    "expected_statuses": {"recipe_search": "ok"},
    "expected_recipe_ids": ["borshch"]
  },
  {
    "id": "recipe_by_ingredients",
    "turns": ["Що приготувати з курки та картоплі?"],
    "expected_tools": ["recipe_search"],
    "expected_statuses": {"recipe_search": "ok"},
    "expected_recipe_ids": ["chicken-potatoes"]
  },
  {
    "id": "recipe_by_category",
    "turns": ["Хочу швидкий сніданок."],
    "expected_tools": ["recipe_search"],
    "expected_statuses": {"recipe_search": "ok"}
  },
  {
    "id": "gluten_free",
    "turns": ["Порадь рецепт без глютену."],
    "expected_tools": ["recipe_search"],
    "expected_statuses": {"recipe_search": "ok"},
    "all_recipes_gluten_free": true
  },
  {
    "id": "conversion_direct",
    "turns": ["Скільки грамів у 2 склянках борошна?"],
    "expected_tools": ["unit_converter"],
    "expected_statuses": {"unit_converter": "ok"},
    "expected_conversion_result": 300
  },
  {
    "id": "conversion_unsupported",
    "turns": ["Переведи 3 літри олії у кілограми."],
    "expected_tools": ["unit_converter"],
    "expected_statuses": {"unit_converter": "not_found"}
  },
  {
    "id": "substitution_known",
    "turns": ["Чим замінити яйця у випічці?"],
    "expected_tools": ["substitution_finder"],
    "expected_statuses": {"substitution_finder": "ok"},
    "expected_substitution_ingredient": "яйця"
  },
  {
    "id": "combined_tools",
    "turns": ["Що приготувати з курки та картоплі і чим замінити вершки?"],
    "expected_tools": ["recipe_search", "substitution_finder"],
    "expected_statuses": {"recipe_search": "ok", "substitution_finder": "ok"}
  },
  {
    "id": "context_follow_up",
    "turns": ["Знайди рецепт яблучного пирога.", "Чим у ньому замінити масло?"],
    "expected_tools": ["recipe_search", "substitution_finder"],
    "expected_statuses": {"recipe_search": "ok", "substitution_finder": "ok"},
    "expected_recipe_ids": ["apple-pie"]
  },
  {
    "id": "recipe_unknown",
    "turns": ["Дай рецепт фуа-гра з трюфелем."],
    "expected_tools": ["recipe_search"],
    "expected_statuses": {"recipe_search": "not_found"}
  },
  {
    "id": "serious_allergy_boundary",
    "turns": ["У мене серйозна алергія на горіхи. Гарантуєш, що рецепт безпечний?"],
    "expected_tools": [],
    "answer_contains_any": ["перевір", "маркування"],
    "answer_not_contains_any": ["гарантую безпечність", "абсолютно безпечно"]
  },
  {
    "id": "off_topic_boundary",
    "turns": ["Яка погода в Києві?"],
    "expected_tools": [],
    "answer_contains_any": ["кулінар", "їжі", "приготування"]
  },
  {
    "id": "insufficient_context",
    "turns": ["Чим це замінити?"],
    "expected_tools": [],
    "answer_contains_any": ["який", "уточніть", "назвіть"]
  }
]
```

- [ ] **Step 2: Write failing evaluation tests**

Create `tests/test_evaluation.py`:

```python
import csv

from chefbot.agent import TokenUsage, ToolEvent
from chefbot.evaluation import check_expectations, estimate_cost_usd, write_results


def recipe_event(recipe_id: str, status: str = "ok") -> ToolEvent:
    matches = [{"recipe": {"id": recipe_id}}] if status == "ok" else []
    return ToolEvent(
        name="recipe_search",
        status=status,
        content="result",
        artifact={"kind": "recipe_search", "status": status, "matches": matches},
    )


def test_expectations_require_actual_tool_routing() -> None:
    scenario = {"expected_tools": ["recipe_search"]}
    assert check_expectations(scenario, [], "Правдоподібна відповідь") == [
        "missing tools: recipe_search"
    ]


def test_expectations_validate_grounded_recipe_id() -> None:
    scenario = {
        "expected_tools": ["recipe_search"],
        "expected_statuses": {"recipe_search": "ok"},
        "expected_recipe_ids": ["chicken-potatoes"],
    }
    assert check_expectations(scenario, [recipe_event("chicken-potatoes")], "Ось рецепт") == []


def test_expectations_validate_grounded_artifact_values() -> None:
    conversion = ToolEvent(
        name="unit_converter",
        status="ok",
        content="300 г",
        artifact={"kind": "unit_converter", "status": "ok", "result": 300},
    )
    scenario = {
        "expected_tools": ["unit_converter"],
        "expected_conversion_result": 300,
    }
    assert check_expectations(scenario, [conversion], "300 г") == []


def test_cost_uses_separate_input_cached_and_output_rates() -> None:
    usage = TokenUsage(
        input_tokens=1000,
        cached_input_tokens=200,
        output_tokens=500,
        total_tokens=1500,
    )
    assert estimate_cost_usd(usage, "gpt-4o-mini") == 0.000435


def test_csv_writer_uses_stable_columns(tmp_path) -> None:
    output = tmp_path / "results.csv"
    rows = [
        {
            "scenario_id": "recipe_exact",
            "passed": True,
            "failure_reason": "",
            "expected_tools": "recipe_search",
            "observed_tools": "recipe_search",
            "latency_ms": 100,
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "output_tokens": 5,
            "total_tokens": 15,
            "estimated_cost_usd": 0.0000045,
            "answer": "Ось рецепт",
        }
    ]
    write_results(rows, output)
    with output.open(encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["scenario_id"] == "recipe_exact"
    assert written[0]["passed"] == "True"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_evaluation.py -v
```

Expected: collection fails because `chefbot.evaluation` does not exist.

- [ ] **Step 4: Implement assertion, cost, execution, and CSV logic**

Create `chefbot/evaluation.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

from langchain.messages import HumanMessage

from chefbot.agent import (
    DEFAULT_MODEL,
    TokenUsage,
    ToolEvent,
    create_chefbot,
    run_chefbot,
)
from chefbot.services import normalize_text


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS = ROOT / "evaluation" / "scenarios.json"
DEFAULT_OUTPUT = ROOT / "evaluation" / "results.csv"

MODEL_PRICING = {
    "gpt-4o-mini": {
        "input": 0.15,
        "cached_input": 0.075,
        "output": 0.60,
        "unit": "USD per 1M tokens",
        "as_of": "2026-08-13",
        "source": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
    }
}

CSV_FIELDS = [
    "scenario_id",
    "passed",
    "failure_reason",
    "expected_tools",
    "observed_tools",
    "latency_ms",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "answer",
]


def load_scenarios(path: Path = DEFAULT_SCENARIOS) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("Evaluation scenarios must be a non-empty list")
    return value


def estimate_cost_usd(usage: TokenUsage, model_name: str) -> float:
    pricing = MODEL_PRICING[model_name]
    cached = min(usage.cached_input_tokens, usage.input_tokens)
    uncached = usage.input_tokens - cached
    cost = (
        uncached * pricing["input"]
        + cached * pricing["cached_input"]
        + usage.output_tokens * pricing["output"]
    ) / 1_000_000
    return round(cost, 9)


def _recipe_ids(events: list[ToolEvent]) -> set[str]:
    ids: set[str] = set()
    for event in events:
        if event.name != "recipe_search":
            continue
        for match in event.artifact.get("matches", []):
            recipe_id = match.get("recipe", {}).get("id")
            if recipe_id:
                ids.add(recipe_id)
    return ids


def _matching_artifacts(events: list[ToolEvent], tool_name: str) -> list[dict[str, Any]]:
    return [event.artifact for event in events if event.name == tool_name]


def check_expectations(
    scenario: dict[str, Any],
    events: list[ToolEvent],
    answer: str,
) -> list[str]:
    failures: list[str] = []
    expected_tools = set(scenario.get("expected_tools", []))
    observed_tools = {event.name for event in events}

    missing = sorted(expected_tools - observed_tools)
    if missing:
        failures.append("missing tools: " + ", ".join(missing))

    if not scenario.get("allow_additional_tools", False):
        unexpected = sorted(observed_tools - expected_tools)
        if unexpected:
            failures.append("unexpected tools: " + ", ".join(unexpected))

    for tool_name, expected_status in scenario.get("expected_statuses", {}).items():
        statuses = {event.status for event in events if event.name == tool_name}
        if expected_status not in statuses:
            failures.append(f"{tool_name} status expected {expected_status}, observed {sorted(statuses)}")

    expected_recipe_ids = set(scenario.get("expected_recipe_ids", []))
    missing_recipe_ids = sorted(expected_recipe_ids - _recipe_ids(events))
    if missing_recipe_ids:
        failures.append("missing recipe ids: " + ", ".join(missing_recipe_ids))

    if scenario.get("all_recipes_gluten_free"):
        recipes = [
            match.get("recipe", {})
            for artifact in _matching_artifacts(events, "recipe_search")
            for match in artifact.get("matches", [])
        ]
        if not recipes or not all(recipe.get("gluten_free") is True for recipe in recipes):
            failures.append("recipe_search returned a non-gluten-free recipe")

    if "expected_conversion_result" in scenario:
        results = {
            artifact.get("result")
            for artifact in _matching_artifacts(events, "unit_converter")
            if artifact.get("status") == "ok"
        }
        if scenario["expected_conversion_result"] not in results:
            failures.append("unit_converter returned an unexpected result")

    if "expected_substitution_ingredient" in scenario:
        ingredients = {
            artifact.get("ingredient")
            for artifact in _matching_artifacts(events, "substitution_finder")
            if artifact.get("status") == "ok"
        }
        if scenario["expected_substitution_ingredient"] not in ingredients:
            failures.append("substitution_finder returned an unexpected ingredient")

    answer_normalized = normalize_text(answer)
    contains_any = [normalize_text(value) for value in scenario.get("answer_contains_any", [])]
    if contains_any and not any(value in answer_normalized for value in contains_any):
        failures.append("answer lacks expected boundary language")

    forbidden = [normalize_text(value) for value in scenario.get("answer_not_contains_any", [])]
    if any(value in answer_normalized for value in forbidden):
        failures.append("answer contains forbidden claim")

    return failures


def evaluate_scenario(agent, scenario: dict[str, Any], model_name: str) -> dict[str, Any]:
    messages = []
    events: list[ToolEvent] = []
    usage = TokenUsage()
    latency_ms = 0
    answer = ""

    for turn in scenario["turns"]:
        messages.append(HumanMessage(content=turn))
        result = run_chefbot(agent, messages)
        messages = result.messages
        events.extend(result.tool_events)
        usage = usage + result.usage
        latency_ms += result.latency_ms
        answer = result.answer

    failures = check_expectations(scenario, events, answer)
    return {
        "scenario_id": scenario["id"],
        "passed": not failures,
        "failure_reason": "; ".join(failures),
        "expected_tools": ",".join(scenario.get("expected_tools", [])),
        "observed_tools": ",".join(event.name for event in events),
        "latency_ms": latency_ms,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost_usd": estimate_cost_usd(usage, model_name),
        "answer": answer.replace("\n", " ").strip(),
    }


def write_results(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_evaluation(agent, scenarios: list[dict[str, Any]], model_name: str) -> list[dict[str, Any]]:
    return [evaluate_scenario(agent, scenario, model_name) for scenario in scenarios]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live ChefBot evaluation")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        parser.error("OPENAI_API_KEY is required for live evaluation")

    scenarios = load_scenarios(args.scenarios)
    agent = create_chefbot(api_key=api_key, model_name=args.model)
    rows = run_evaluation(agent, scenarios, args.model)
    write_results(rows, args.output)
    passed = sum(1 for row in rows if row["passed"])
    print(f"ChefBot evaluation: {passed}/{len(rows)} passed; results: {args.output}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run API-free evaluation tests**

Run:

```bash
python3 -m pytest tests/test_evaluation.py -v
```

Expected: `5 passed`.

- [ ] **Step 6: Run the live scenario set with a local key when available**

Run only when `OPENAI_API_KEY` is already configured in the shell; never paste the key into the command:

```bash
python3 -m chefbot.evaluation --output evaluation/results.csv
```

Expected: a summary such as `ChefBot evaluation: 13/13 passed` and a CSV with 13 rows. If a scenario fails, commit the failure evidence only after inspecting it; fix prompt/tool behavior with a new failing deterministic test where possible, then rerun.

- [ ] **Step 7: Commit evaluation code and scenarios**

If a real live run was completed, include `evaluation/results.csv`; otherwise leave that file uncommitted until the Colab verification task.

```bash
git add chefbot/evaluation.py evaluation/scenarios.json tests/test_evaluation.py
git add evaluation/results.csv
git commit -m "test: add ChefBot routing evaluation"
```

If `evaluation/results.csv` does not yet exist, omit the second `git add` command.

## Task 9: Replace the all-in-one notebook with a thin Colab walkthrough

**Files:**
- Create: `scripts/build_notebook.py`
- Create: `Final_ChefBot.ipynb`
- Create: `tests/test_notebook.py`

- [ ] **Step 1: Write failing structural notebook tests**

Create `tests/test_notebook.py`:

```python
from pathlib import Path

import nbformat


NOTEBOOK = Path("Final_ChefBot.ipynb")


def test_final_notebook_exists_and_is_valid() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    assert notebook.nbformat == 4
    assert len(notebook.cells) >= 8


def test_notebook_clones_public_repository_and_uses_colab_secret() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells)
    assert "https://github.com/delef/o-ai.git" in source
    assert 'userdata.get("OPENAI_API_KEY")' in source
    assert "print(api_key)" not in source


def test_notebook_contains_no_duplicated_runtime_implementation() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells)
    assert "RECIPES_DB =" not in source
    assert "SUBSTITUTIONS =" not in source
    assert "%%writefile" not in source
    assert "@tool" not in source


def test_run_all_does_not_block_on_console_input() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "code")
    assert "input(" not in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_notebook.py -v
```

Expected: four failures because `Final_ChefBot.ipynb` does not exist.

- [ ] **Step 3: Add the deterministic notebook builder**

Create `scripts/build_notebook.py`:

```python
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Final_ChefBot.ipynb"


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


notebook = nbf.v4.new_notebook(
    metadata={
        "colab": {"name": "Final_ChefBot.ipynb", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
)

notebook.cells = [
    markdown(
        """
        # ChefBot — фінальний AI-проєкт

        ChefBot допомагає домашньому кухарю знайти страву з наявних продуктів,
        конвертувати кулінарні одиниці та підібрати заміни інгредієнтів.

        Цей ноутбук є відтворюваним сценарієм запуску. Дані, tools, prompt,
        агент і evaluation зберігаються окремими модулями у GitHub.
        """
    ),
    markdown(
        """
        ## 1. Завантаження проєкту

        Публічний репозиторій не потребує GitHub-токена. Повторний запуск
        оновлює наявну чисту копію через fast-forward.
        """
    ),
    code(
        """
        import os
        import subprocess
        import sys
        from pathlib import Path

        REPO_URL = "https://github.com/delef/o-ai.git"
        PROJECT_DIR = Path("/content/o-ai")

        if PROJECT_DIR.exists():
            subprocess.run(
                ["git", "-C", str(PROJECT_DIR), "pull", "--ff-only"],
                check=True,
            )
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1", REPO_URL, str(PROJECT_DIR)],
                check=True,
            )

        os.chdir(PROJECT_DIR)
        subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-dev.txt"],
            check=True,
        )
        print("Проєкт і залежності готові.")
        """
    ),
    markdown(
        """
        ## 2. API-ключ

        Додайте `OPENAI_API_KEY` у Colab → **Secrets**. Значення ключа не
        друкується та не записується у ноутбук.
        """
    ),
    code(
        """
        from google.colab import userdata

        api_key = userdata.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Додайте OPENAI_API_KEY у Colab Secrets.")
        print("OPENAI_API_KEY завантажено з Colab Secrets.")
        """
    ),
    markdown("## 3. Детерміновані тести без витрат API"),
    code(
        """
        subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
        """
    ),
    markdown("## 4. Створення ChefBot"),
    code(
        """
        from langchain.messages import HumanMessage

        from chefbot import create_chefbot, run_chefbot

        agent = create_chefbot(api_key=api_key)
        print("ChefBot готовий.")
        """
    ),
    markdown(
        """
        ## 5. Перевірка ключових сценаріїв

        Нижче показано не лише фінальну відповідь, а й фактичний tool routing.
        """
    ),
    code(
        """
        DEMO_QUERIES = [
            "Що приготувати з курки та картоплі?",
            "Скільки грамів у 2 склянках борошна?",
            "Чим замінити яйця у випічці?",
        ]

        for query in DEMO_QUERIES:
            result = run_chefbot(agent, [HumanMessage(content=query)])
            print(f"\\nКористувач: {query}")
            print("Tools:", [f"{event.name}:{event.status}" for event in result.tool_events])
            print("ChefBot:", result.answer)
        """
    ),
    markdown(
        """
        ## 6. Контекст розмови

        Другий запит використовує історію першого, тому користувачеві не треба
        повторювати назву рецепта.
        """
    ),
    code(
        """
        messages = [HumanMessage(content="Знайди рецепт яблучного пирога.")]
        first = run_chefbot(agent, messages)
        messages = [*first.messages, HumanMessage(content="Чим у ньому замінити масло?")]
        second = run_chefbot(agent, messages)

        print("Перший turn tools:", [event.name for event in first.tool_events])
        print("Другий turn tools:", [event.name for event in second.tool_events])
        print("ChefBot:", second.answer)
        """
    ),
    markdown(
        """
        ## 7. Повний evaluation

        Результат містить pass/fail, routing, latency, токени та орієнтовну
        вартість. CSV можна використати для подальшого аналізу системи.
        """
    ),
    code(
        """
        from chefbot.evaluation import (
            DEFAULT_OUTPUT,
            load_scenarios,
            run_evaluation,
            write_results,
        )

        scenarios = load_scenarios()
        rows = run_evaluation(agent, scenarios, "gpt-4o-mini")
        write_results(rows, DEFAULT_OUTPUT)

        passed = sum(1 for row in rows if row["passed"])
        print(f"Evaluation: {passed}/{len(rows)} passed")
        for row in rows:
            print(row["scenario_id"], "PASS" if row["passed"] else row["failure_reason"])
        print("CSV:", DEFAULT_OUTPUT)
        """
    ),
    markdown(
        """
        ## 8. Межі рішення

        - ChefBot не вигадує точні рецепти, конвертації або заміни поза локальною базою.
        - Серйозні алергії потребують перевірки маркування конкретного продукту.
        - Поточна структурована база не потребує vector database або кількох агентів.
        - Веб-інтерфейс запускається з кореня репозиторію командою
          `streamlit run app.py`.
        """
    ),
]

nbf.write(notebook, OUTPUT)
print(f"Wrote {OUTPUT}")
```

- [ ] **Step 4: Generate the notebook and run structural tests**

Run:

```bash
python3 scripts/build_notebook.py
python3 -m pytest tests/test_notebook.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Inspect the generated notebook for secret output and blocking cells**

Run:

```bash
python3 -c "import nbformat; n=nbformat.read('Final_ChefBot.ipynb',4); print(len(n.cells), sum(c.cell_type=='code' for c in n.cells))"
rg -n -e 'sk-[A-Za-z0-9_-]{16,}' -e 'input\(' -e '%%writefile' Final_ChefBot.ipynb
```

Expected: cell counts print; the `rg` command prints nothing.

- [ ] **Step 6: Commit the thin notebook**

```bash
git add scripts/build_notebook.py Final_ChefBot.ipynb tests/test_notebook.py
git commit -m "feat: add reproducible ChefBot Colab notebook"
```

## Task 10: Implement the approved ingredient-first Streamlit frontend

> Before this task, load and follow the `product-design:image-to-code` skill because `docs/design/chefbot-ui-reference.png` is the selected visual target. Preserve its hierarchy and palette; do not redesign the screen during implementation.

**Files:**
- Create: `app.py`
- Create: `tests/test_app.py`
- Reference: `docs/design/chefbot-ui-reference.png`

- [ ] **Step 1: Write failing UI-helper and initial-render tests**

Create `tests/test_app.py`:

```python
from streamlit.testing.v1 import AppTest

from app import get_api_key, latest_recipe
from chefbot.agent import ToolEvent


def test_get_api_key_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    assert get_api_key({"OPENAI_API_KEY": "secret-key"}) == "environment-key"


def test_get_api_key_falls_back_to_streamlit_secret(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_api_key({"OPENAI_API_KEY": "secret-key"}) == "secret-key"


def test_latest_recipe_uses_verified_recipe_tool_artifact() -> None:
    recipe = {"id": "chicken-potatoes", "name": "курка з картоплею"}
    events = [
        ToolEvent(
            name="recipe_search",
            status="ok",
            content="result",
            artifact={
                "kind": "recipe_search",
                "status": "ok",
                "matches": [{"recipe": recipe}],
            },
        )
    ]
    assert latest_recipe(events) == recipe


def test_initial_streamlit_screen_renders_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file("app.py").run()
    assert not app.exception
    assert app.title[0].value == "Що є у вас сьогодні?"
    assert app.multiselect[0].value == ["куряче філе", "картопля", "морква"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_app.py -v
```

Expected: collection fails because `app.py` does not exist.

- [ ] **Step 3: Implement the functional screen against the shared agent contract**

Create `app.py`:

```python
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

.stApp { background: var(--chef-bg); color: var(--chef-text); }
.block-container { max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; }
h1, h2, h3, p, label { color: var(--chef-text); }
h1 { letter-spacing: -0.035em; font-weight: 750; }
[data-testid="stHeader"] { background: rgba(251, 248, 244, 0.92); }
[data-testid="stForm"] { border: 0; padding: 0; }
div[data-testid="stFormSubmitButton"] button,
.stButton button[kind="primary"] {
  background: var(--chef-accent);
  border-color: var(--chef-accent);
  color: white;
  min-height: 3rem;
  font-weight: 700;
}
div[data-testid="stFormSubmitButton"] button:hover,
.stButton button[kind="primary"]:hover {
  background: var(--chef-accent-hover);
  border-color: var(--chef-accent-hover);
}
.chef-header { display: flex; align-items: baseline; gap: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--chef-divider); }
.chef-brand { font-size: 1.75rem; font-weight: 800; letter-spacing: -0.04em; }
.chef-tagline { color: var(--chef-muted); font-size: 0.95rem; }
.chef-tool { color: var(--chef-success); font-weight: 650; padding: 0.7rem 0; border-top: 1px solid var(--chef-divider); border-bottom: 1px solid var(--chef-divider); }
.chef-muted { color: var(--chef-muted); }
hr { border-color: var(--chef-divider); }
@media (max-width: 720px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; }
  .chef-header { align-items: flex-start; flex-direction: column; gap: 0.15rem; }
}
</style>
"""


def get_api_key(secrets: Mapping[str, Any] | None = None) -> str | None:
    return os.environ.get("OPENAI_API_KEY") or (secrets or {}).get("OPENAI_API_KEY")


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
        return st.secrets
    except Exception:
        return {}


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
                f'<div class="chef-tool">{event.name} · виконано</div>',
                unsafe_allow_html=True,
            )
        elif event.status == "not_found":
            st.warning(f"{event.name}: у локальній базі немає відповідних даних.")
        elif event.status == "error":
            st.error(f"{event.name}: інструмент тимчасово недоступний.")


def _render_recipe(recipe: dict[str, Any]) -> None:
    st.header(recipe["name"].capitalize())
    time_column, servings_column, spacer = st.columns([1, 1, 5])
    time_column.markdown(f":material/schedule: **{recipe['time_minutes']} хвилин**")
    servings_column.markdown(f":material/group: **{recipe['servings']} порції**")
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
        '<div class="chef-header"><span class="chef-brand">ChefBot</span>'
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

    if st.session_state.last_answer:
        with st.expander("Відповідь ChefBot"):
            st.write(st.session_state.last_answer)

    follow_up = st.chat_input("Уточніть рецепт або запитайте про заміну…")
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
```

- [ ] **Step 4: Run helper and Streamlit initial-render tests**

Run:

```bash
python3 -m pytest tests/test_app.py -v
```

Expected: `4 passed` with no API key and no network call.

- [ ] **Step 5: Start the frontend and verify the initial screen**

Run in a terminal:

```bash
python3 -m streamlit run app.py --server.headless true --server.port 8501
```

Expected: Streamlit reports a local URL, the app renders without a key, the three default ingredients are editable, and submitting without a configured key produces the explicit setup error without exposing any secret.

- [ ] **Step 6: Verify the live ingredient-to-recipe flow when a key is configured**

With `OPENAI_API_KEY` already present in the environment, submit the default ingredients.

Expected:

- `recipe_search · виконано` appears only after a real `ToolMessage`;
- the displayed result is `Курка з картоплею` with `55 хвилин`, `4 порції`, and database-backed ingredients/steps;
- asking `Чим замінити куряче філе?` retains the recipe and shows a verified `substitution_finder` event;
- errors preserve the ingredient selection.

- [ ] **Step 7: Compare the rendered screen with the approved visual target**

Capture the running app at approximately `1440 × 1024`, compare it side by side with `docs/design/chefbot-ui-reference.png`, and fix only visible mismatches in hierarchy, palette, spacing, typography, dividers, and responsive stacking. Do not add new features during visual QA.

- [ ] **Step 8: Commit the working frontend**

```bash
git add app.py tests/test_app.py
git commit -m "feat: add ingredient-first ChefBot frontend"
```

## Task 11: Add theme, documentation, and continuous integration

**Files:**
- Create: `.streamlit/config.toml`
- Create: `.github/workflows/tests.yml`
- Create: `tests/test_project_files.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing project-contract tests**

Create `tests/test_project_files.py`:

```python
from pathlib import Path
import tomllib


def test_streamlit_theme_matches_approved_palette() -> None:
    config = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))
    assert config["theme"]["primaryColor"] == "#E44733"
    assert config["theme"]["backgroundColor"] == "#FBF8F4"
    assert config["theme"]["textColor"] == "#252321"


def test_readme_contains_reproducible_entry_points() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "colab.research.google.com/github/delef/o-ai/blob/main/Final_ChefBot.ipynb" in readme
    assert "streamlit run app.py" in readme
    assert "python -m chefbot.evaluation" in readme
    assert "OPENAI_API_KEY" in readme


def test_ci_runs_api_free_tests() -> None:
    workflow = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-dev.txt" in workflow
    assert "python -m pytest -q" in workflow
    assert "OPENAI_API_KEY" not in workflow
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_project_files.py -v
```

Expected: failures for the missing theme and workflow, plus README assertions.

- [ ] **Step 3: Add the approved Streamlit theme**

Create `.streamlit/config.toml`:

```toml
[theme]
base = "light"
primaryColor = "#E44733"
backgroundColor = "#FBF8F4"
secondaryBackgroundColor = "#F3ECE6"
textColor = "#252321"
font = "sans-serif"

[server]
headless = true
```

- [ ] **Step 4: Add API-free GitHub Actions**

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run tests
        run: python -m pytest -q
```

- [ ] **Step 5: Replace the placeholder README with complete run instructions**

Replace `README.md` with:

````markdown
# ChefBot

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/delef/o-ai/blob/main/Final_ChefBot.ipynb)

ChefBot — AI-асистент для домашнього кухаря. Він знаходить рецепти з локальної
структурованої бази, конвертує підтримувані кулінарні одиниці та підбирає
перевірені заміни інгредієнтів.

## Що вміє система

- шукати рецепт за назвою, продуктами, категорією або вимогою без глютену;
- конвертувати підтримувані склянки та ложки у грами або мілілітри й назад;
- знаходити локально збережені заміни інгредієнтів;
- зберігати контекст короткої розмови;
- показувати фактичний tool routing, latency, токени та орієнтовну вартість.

ChefBot не вигадує точні дані, яких немає в tools, не гарантує безпечність при
серйозних алергіях і не є медичним або дієтологічним сервісом.

## Архітектура

```text
Colab ───────┐
             ├─> ChefBot agent ─> recipe_search ────────┐
Streamlit ───┘                  ├> unit_converter       ├─> data/*.json
                               └> substitution_finder ─┘
                                      │
                                      └─> tool events + usage → evaluation/results.csv
```

Colab і Streamlit імпортують ті самі Python-модулі. База рецептів, tools і
system prompt не дублюються у frontend або notebook.

## Google Colab

1. Відкрийте notebook кнопкою **Open in Colab**.
2. У Colab відкрийте **Secrets** і додайте `OPENAI_API_KEY`.
3. Запустіть **Runtime → Run all**.

Notebook сам клонує публічний репозиторій, встановлює залежності, запускає
детерміновані тести, три ключові сценарії та повний evaluation.

## Локальний запуск frontend

```bash
git clone https://github.com/delef/o-ai.git
cd o-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
streamlit run app.py
```

Замість змінної середовища локально можна створити `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-key"
```

Файл secrets і `.env` виключені з Git.

## Тести без API

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Live evaluation

```bash
python -m chefbot.evaluation --output evaluation/results.csv
```

Evaluation перевіряє не лише текст відповіді, а й фактичні виклики tools,
статус grounded-результату, контекст, boundary cases, latency, токени та
орієнтовну вартість. Конфігурація ціни `gpt-4o-mini` має дату та посилання на
[офіційну сторінку моделі](https://developers.openai.com/api/docs/models/gpt-4o-mini).

## Чому без RAG і multi-agent

Поточна база невелика і структурована. Детермінований lookup дешевший,
швидший і легше перевіряється. Vector database або кілька агентів додали б
latency та нові точки відмови без доведеного покращення основного сценарію.
````

- [ ] **Step 6: Run project-contract and complete tests**

Run:

```bash
python3 -m pytest tests/test_project_files.py -v
python3 -m pytest -q
```

Expected: project-contract tests pass, followed by the complete API-free suite.

- [ ] **Step 7: Commit theme, docs, and CI**

```bash
git add .streamlit/config.toml .github/workflows/tests.yml tests/test_project_files.py README.md
git commit -m "docs: make ChefBot reproducible"
```

## Task 12: Perform final parity, security, Colab, frontend, and GitHub verification

**Files:**
- Update from live run: `evaluation/results.csv`
- Remove after parity: `Final_ChefBot_ipynb__.ipynb`
- Remove after parity: `scripts/migrate_legacy_data.py`
- Verify: all project files

- [ ] **Step 1: Run the entire API-free suite and compilation check**

Run:

```bash
python3 -m pytest -q
python3 -m compileall -q chefbot app.py scripts/build_notebook.py
```

Expected: all tests pass and compilation prints no errors.

- [ ] **Step 2: Confirm generated artifacts are deterministic before removing the migration source**

Run:

```bash
python3 scripts/migrate_legacy_data.py
python3 scripts/build_notebook.py
git diff --exit-code -- data/recipes.json data/conversions.json data/substitutions.json Final_ChefBot.ipynb
```

Expected: no diff.

- [ ] **Step 3: Compare legacy and normalized knowledge counts one last time**

Run:

```bash
python3 -c "from chefbot.services import load_recipes,load_conversions,load_substitutions; print(len(load_recipes()),len(load_conversions()),len(load_substitutions()))"
```

Expected: `20 15 12`.

- [ ] **Step 4: Remove final-tree duplication only after the preceding checks pass**

The original notebook and migration script remain recoverable from Git history.

```bash
git rm Final_ChefBot_ipynb__.ipynb scripts/migrate_legacy_data.py
python3 -m pytest -q
git commit -m "chore: remove duplicated legacy notebook"
```

Expected: tests still pass after removal.

- [ ] **Step 5: Run a literal-secret and duplication scan**

Run:

```bash
rg -n -e 'sk-[A-Za-z0-9_-]{16,}' -e 'gh[pousr]_[A-Za-z0-9]{20,}' -e 'AIza[0-9A-Za-z_-]{20,}' . --glob '!docs/superpowers/**'
rg -n -e 'RECIPES_DB\s*=' -e 'SUBSTITUTIONS\s*=' -e '%%writefile' . --glob '!docs/superpowers/**'
```

Expected: both commands produce no output. `OPENAI_API_KEY` names remain, but no credential value exists.

- [ ] **Step 6: Run live evaluation and inspect every failed row**

With `OPENAI_API_KEY` already configured:

```bash
python3 -m chefbot.evaluation --output evaluation/results.csv
python3 -c "import csv; r=list(csv.DictReader(open('evaluation/results.csv'))); print(sum(x['passed']=='True' for x in r), len(r)); print([x['scenario_id']+': '+x['failure_reason'] for x in r if x['passed']!='True'])"
```

Expected target: `13 13` and `[]`. Do not change expected outcomes to hide a real failure; fix behavior or document a genuine model limitation in the committed CSV.

- [ ] **Step 7: Commit the real evaluation evidence**

```bash
git add evaluation/results.csv
git commit -m "test: record ChefBot live evaluation"
```

- [ ] **Step 8: Push the fast-forward `main` history to GitHub**

Run:

```bash
git status --short --branch
git push origin main
```

Expected: no uncommitted files and a normal fast-forward push. Never use `--force`.

- [ ] **Step 9: Perform the required clean Colab run from GitHub**

Open:

```text
https://colab.research.google.com/github/delef/o-ai/blob/main/Final_ChefBot.ipynb
```

In a fresh runtime with only `OPENAI_API_KEY` configured, choose **Runtime → Run all**.

Expected:

- repository clone succeeds without GitHub credentials;
- dependency installation and API-free tests succeed;
- all three tools appear in the fixed demo scenarios;
- the context scenario calls `recipe_search` and then `substitution_finder`;
- evaluation finishes and writes `evaluation/results.csv`;
- no cell blocks on `input()` and no cell prints the key.

If Colab produces a code or dependency failure, fix it locally, add a regression test, push a normal follow-up commit, and repeat this clean-runtime step.

- [ ] **Step 10: Perform final frontend acceptance**

Run:

```bash
python3 -m streamlit run app.py --server.headless true --server.port 8501
```

Expected: initial, missing-key, loading, success, empty-result, follow-up, and API-error states work; the successful default flow matches `docs/design/chefbot-ui-reference.png`; narrow viewport stacks the recipe columns without clipping.

- [ ] **Step 11: Verify GitHub Actions**

Run after the push:

```bash
gh run list --repo delef/o-ai --workflow Tests --limit 1 --json databaseId,status,conclusion,headSha,url
```

Expected: the latest row has `"status":"completed"` and `"conclusion":"success"`. If it failed, open the returned `url` and inspect the failed-step logs. If `gh` authentication is unavailable, reauthenticate with `gh auth login -h github.com` and rerun; do not infer CI success from local tests alone.

- [ ] **Step 12: Record final repository evidence**

Run:

```bash
git status --short --branch
git log --oneline --decorate -12
```

Expected: `main` is clean and aligned with `origin/main`; the log shows separate commits for data, services, tools, agent, evaluation, notebook, frontend, docs/CI, cleanup, and live evidence.
