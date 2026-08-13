# ChefBot: project design

Date: 2026-08-13  
Status: approved for implementation

## Objective

Turn the current all-in-one Colab notebook into a reproducible GitHub project while keeping Google Colab as the primary execution environment. The finished technical project must:

- run from a clean Colab runtime when `OPENAI_API_KEY` is available;
- keep data, deterministic logic, agent configuration, evaluation, and UI in separate files;
- visibly and verifiably route relevant requests through ChefBot tools;
- provide a working Streamlit frontend for the main user journey;
- produce test and usage evidence that can later support the final presentation;
- avoid unnecessary RAG or multi-agent complexity when the local structured data is sufficient.

Presentation slides, demo recording, public deployment, and the defense script are outside this implementation phase.

## Product boundary

ChefBot helps a home cook:

1. find a recipe by dish, available ingredients, category, or a supported dietary constraint;
2. convert supported culinary units;
3. find supported ingredient substitutions;
4. continue a short conversation while retaining the current context.

ChefBot does not invent database-backed facts when a tool returns no result. It does not provide medical or therapeutic diets, guarantee allergen safety, answer unrelated general-purpose questions, or expose model chain-of-thought.

## Key design decisions

### Colab remains the primary entry point

The notebook is a thin, readable product walkthrough rather than the source of all implementation. Its first section clones the public repository and installs pinned dependencies. It then reads `OPENAI_API_KEY` from Colab Secrets, imports the package, runs deterministic checks, creates the agent, and exercises the selected scenarios.

This satisfies the required notebook artifact while preventing code duplication between Colab and the frontend.

### One agent with three deterministic tools

The project keeps one LLM agent and these tools:

- `recipe_search`;
- `unit_converter`;
- `substitution_finder`.

The current product scope does not justify RAG or multiple agents. The source data is small and structured, deterministic lookup is cheaper and easier to test, and an additional orchestration layer would add latency and failure modes without improving the core user outcome.

### Structured tool results drive the interface

Tool implementations use pure deterministic service functions. Tool wrappers return model-readable content plus structured result data. The frontend renders the structured result instead of parsing free-form LLM prose. This keeps recipe quantities, timings, and substitutions grounded in the repository data.

Only the tool name, status, and result may be shown to the user. Internal reasoning is never displayed.

## Repository structure

```text
o-ai/
├── Final_ChefBot.ipynb
├── chefbot/
│   ├── __init__.py
│   ├── agent.py
│   ├── evaluation.py
│   ├── prompt.py
│   ├── services.py
│   └── tools.py
├── data/
│   ├── conversions.json
│   ├── recipes.json
│   └── substitutions.json
├── evaluation/
│   ├── scenarios.json
│   └── results.csv
├── tests/
│   ├── test_evaluation.py
│   └── test_services.py
├── .github/workflows/tests.yml
├── .streamlit/config.toml
├── app.py
├── requirements.txt
├── requirements-dev.txt
├── README.md
└── .gitignore
```

The LMS copy can be renamed to the required `Final_Прізвище_Варіант.ipynb` format before submission without changing its contents.

## Components

### Data

`data/*.json` is the single source of truth.

- Recipes use stable IDs and structured ingredients with name, amount, and unit.
- Recipe search fields include name, tags, ingredients, dietary flags, and a small curated alias list for relevant Ukrainian word forms.
- Conversions use explicit source unit, target unit, product where required, and numeric factor. Safe inverse conversions are generated only when the original conversion is valid and non-zero.
- Substitutions preserve the substitute, supported use, and caution text.

Data is loaded and validated before it reaches a tool. Invalid or incomplete records fail clearly during startup or tests instead of producing a partially grounded answer.

### Deterministic services

`chefbot/services.py` contains API-free functions for recipe ranking, unit conversion, and substitution lookup. These functions do not import LangChain and are the main unit-test boundary.

Recipe ranking is deterministic. Exact name matches rank first, followed by matching ingredients, dietary constraints, and tags. The result includes match reasons so evaluation can explain why a recipe was selected.

### Tool wrappers

`chefbot/tools.py` exposes the three services as LangChain tools with narrow schemas and truthful descriptions. Unsupported requests return an explicit no-result or clarification response. Tool descriptions and the system prompt must not promise conversions or searches that the implementation does not support.

### Agent

`chefbot/agent.py` creates the model and agent only when called; importing the package never requires an API key. The factory accepts the key and model configuration explicitly, applies timeouts, and registers the three tools.

`chefbot/prompt.py` owns one system prompt. It requires a relevant tool for grounded operations, preserves conversational context, keeps answers concise, uses Ukrainian by default, distinguishes tool evidence from general explanation, and enforces the product boundary.

### Evaluation

`chefbot/evaluation.py` runs named scenarios and records:

- expected and observed tool names;
- deterministic assertions against the tool result;
- response status;
- latency;
- input, output, and total tokens when supplied by the model;
- estimated request cost using a clearly dated pricing configuration;
- concise failure reason.

`evaluation/scenarios.json` includes successful, boundary, failure, and multi-turn cases. `evaluation/results.csv` is regenerated by the live evaluation command and provides evidence for later analysis. It must not contain secrets or private user content.

### Frontend

The frontend is a Streamlit application backed by the same package and data as Colab. The approved visual reference is [`docs/design/chefbot-ui-reference.png`](../../design/chefbot-ui-reference.png).

The primary screen is ingredient-first:

1. the user adds or removes ingredient chips;
2. `Знайти страву` sends a grounded request to the agent;
3. the UI shows a compact `recipe_search · виконано` state after a verified tool call;
4. a structured recipe view shows the title, time, portions, ingredients, and preparation steps;
5. a follow-up field continues the same conversation and supports recipe clarification or substitution questions.

Visual contract:

- warm off-white base surface;
- charcoal typography;
- restrained tomato-red primary action and interactive accents;
- herb-green tool-success indicator;
- thin warm-gray separators and almost no shadows;
- desktop two-column recipe layout that stacks cleanly on narrow screens;
- accessible labels, keyboard operation, visible focus, and sufficient contrast;
- icons come from a maintained icon library rather than handcrafted graphics.

The UI has explicit initial, loading, success, empty-result, missing-key, and API-error states. It never shows a success tool badge unless the corresponding tool call is present in the agent messages.

## Data flow

```text
Colab notebook ─┐
                ├─> agent factory ─> LLM ─> tool wrapper ─> deterministic service ─> JSON data
Streamlit app ──┘                      │
                                      └─> response + tool event + usage metadata
                                                          │
                                  ┌───────────────────────┴──────────────────────┐
                                  v                                              v
                         structured UI result                           evaluation CSV
```

Colab and Streamlit never carry their own copies of recipes, tools, or the system prompt.

## Error handling and security

- Colab reads the key only through `google.colab.userdata`; the frontend reads environment or Streamlit secrets.
- The key is never printed, written to a notebook output, committed, or stored in evaluation results.
- Missing keys produce setup guidance before agent creation.
- Model timeouts, rate limits, and connection errors produce a concise retryable UI error while preserving the current input.
- Empty ingredients, unsupported conversions, unknown substitutions, and no recipe match produce specific user-facing states rather than fabricated values.
- Unexpected tool-result shapes are logged as evaluation failures and rendered as a safe generic error.
- `.gitignore` excludes local environments, caches, secret files, Streamlit secrets, and generated temporary artifacts.

## Testing strategy

### Deterministic tests without an API key

Unit tests cover:

- data schema and unique recipe IDs;
- exact and partial recipe matches;
- ingredient, tag, and gluten-free filtering;
- supported direct and inverse conversions;
- invalid numbers, missing products, and unsupported units;
- known and unknown substitutions;
- stable ranking and no-result behavior;
- evaluation pass/fail calculations and CSV shape.

These tests run locally and in GitHub Actions on every push.

### Live agent evaluation with an API key

The live suite covers at least:

- each of the three tools;
- combined tool use;
- a multi-turn contextual follow-up;
- an unknown recipe;
- an unsupported conversion;
- a serious-allergy boundary;
- an off-topic request;
- malformed or insufficient input.

A scenario passes only when the expected tool routing and grounded result assertions pass. A plausible final answer without the required tool call is a failure.

### Reproducibility check

Before declaring the project complete, run the notebook from a fresh Colab runtime with only `OPENAI_API_KEY` configured. `Run all` must finish without manual file uploads or edits. The Streamlit app must also start from the documented command and complete the ingredient-to-recipe flow.

## Implementation sequence

1. Extract and normalize data while preserving the current notebook as the parity reference.
2. Build deterministic services and their unit tests.
3. Add LangChain tool wrappers, prompt, and agent factory.
4. Add evaluation scenarios, routing checks, usage capture, and CSV output.
5. Replace the all-in-one notebook with the thin Colab walkthrough.
6. Implement the approved Streamlit frontend against the same agent response contract.
7. Add README, pinned dependencies, secret handling, `.gitignore`, and GitHub Actions.
8. Verify unit tests, live evaluation, frontend behavior, and a clean Colab run.
9. Remove the legacy duplicated notebook code only after parity is demonstrated.

## Acceptance criteria

The technical project is complete when all of the following are true:

- no recipe database, tool implementation, or system prompt is duplicated in the notebook or frontend;
- a clean Colab `Run all` succeeds with an API key;
- all deterministic tests pass without an API key;
- live scenarios record actual tool routing, latency, tokens, and pass/fail evidence;
- the approved ingredient-first Streamlit flow works and matches the visual contract;
- missing or unsupported data never causes ChefBot to invent exact values;
- the repository contains no credentials;
- README instructions reproduce both Colab and Streamlit execution;
- GitHub Actions passes on the public repository.
