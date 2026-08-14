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


def _has_complete_recipe_revision(events: list[ToolEvent], ingredient: str) -> bool:
    expected_ingredient = normalize_text(ingredient)
    for artifact in _matching_artifacts(events, "recipe_editor"):
        ingredients = artifact.get("ingredients")
        steps = artifact.get("steps")
        if not isinstance(ingredients, list) or not ingredients:
            continue
        if not isinstance(steps, list) or not all(isinstance(step, str) and step.strip() for step in steps):
            continue
        names = [
            normalize_text(str(item.get("name", "")))
            for item in ingredients
            if isinstance(item, dict)
        ]
        if len(names) == len(ingredients) and expected_ingredient in names:
            return True
    return False


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

    if "expected_recipe_revision_ingredient" in scenario:
        ingredient = str(scenario["expected_recipe_revision_ingredient"])
        if not _has_complete_recipe_revision(events, ingredient):
            failures.append(
                f"recipe_editor did not return a complete revision for {ingredient}"
            )

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
