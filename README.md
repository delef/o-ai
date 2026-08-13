# ChefBot

[![Tests](https://github.com/delef/o-ai/actions/workflows/tests.yml/badge.svg)](https://github.com/delef/o-ai/actions/workflows/tests.yml)
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
Streamlit ───┘                 ├> unit_converter        ├─> data/*.json
                               └> substitution_finder  ─┘
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
