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
