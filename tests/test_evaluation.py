import csv

from chefbot.agent import TokenUsage, ToolEvent
from chefbot.evaluation import check_expectations, estimate_cost_usd, load_scenarios, write_results


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


def test_expectations_reject_an_incomplete_recipe_revision() -> None:
    revision = ToolEvent(
        name="recipe_editor",
        status="ok",
        content="Рецепт оновлено.",
        artifact={
            "kind": "recipe_editor",
            "status": "ok",
            "reason": "Ви попросили додати цибулю.",
            "ingredients": [
                {"name": "куряче філе", "quantity": 500, "unit": "г", "note": None},
                {"name": "цибуля", "quantity": 1, "unit": "шт.", "note": None},
            ],
        },
    )
    scenario = {
        "expected_tools": ["recipe_editor"],
        "expected_recipe_revision_ingredient": "цибуля",
    }

    assert check_expectations(scenario, [revision], "Рецепт оновлено.") == [
        "recipe_editor did not return a complete revision for цибуля"
    ]


def test_live_evaluation_covers_recipe_revision() -> None:
    scenarios = {scenario["id"]: scenario for scenario in load_scenarios()}

    assert scenarios["recipe_revision"]["expected_tools"] == [
        "recipe_search",
        "recipe_editor",
    ]
    assert scenarios["recipe_revision"]["expected_recipe_revision_ingredient"] == "цибуля"


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
