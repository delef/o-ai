from pathlib import Path
from textwrap import dedent

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Final_ChefBot.ipynb"


def markdown(source: str):
    return nbf.v4.new_markdown_cell(dedent(source).strip())


def code(source: str):
    return nbf.v4.new_code_cell(dedent(source).strip())


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
        ## 6. Контекст розмови та цілісне оновлення рецепта

        Другий запит використовує історію першого, тому користувачеві не треба
        повторювати назву рецепта. `recipe_editor` повертає повний оновлений
        склад і всі кроки, а не частковий патч.
        """
    ),
    code(
        """
        messages = [HumanMessage(content="Знайди рецепт курки з картоплею.")]
        first = run_chefbot(agent, messages)
        messages = [
            *first.messages,
            HumanMessage(content="Додай до рецепта 1 цибулину і онови весь рецепт."),
        ]
        second = run_chefbot(agent, messages)
        revisions = [
            event.artifact
            for event in second.tool_events
            if event.name == "recipe_editor" and event.status == "ok"
        ]

        print("Перший turn tools:", [event.name for event in first.tool_events])
        print("Другий turn tools:", [event.name for event in second.tool_events])
        if not revisions:
            raise RuntimeError("recipe_editor не повернув цілісне оновлення рецепта.")
        revision = revisions[-1]
        print("Оновлені інгредієнти:", revision["ingredients"])
        print("Оновлені кроки:", revision["steps"])
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
        from IPython.display import display
        import pandas as pd

        display(
            pd.DataFrame(rows)[
                [
                    "scenario_id",
                    "passed",
                    "observed_tools",
                    "latency_ms",
                    "total_tokens",
                    "estimated_cost_usd",
                    "failure_reason",
                ]
            ]
        )
        print("CSV:", DEFAULT_OUTPUT)

        def download_results():
            from google.colab import files

            files.download(str(DEFAULT_OUTPUT))

        print("Для завантаження CSV виконайте: download_results()")
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

for index, cell in enumerate(notebook.cells):
    cell["id"] = f"chefbot-{index:02d}"

nbf.write(notebook, OUTPUT)
print(f"Wrote {OUTPUT}")
