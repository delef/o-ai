import ast
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


def test_notebook_covers_recipe_revision_and_exposes_results_download() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells)

    assert "Додай до рецепта 1 цибулину і онови весь рецепт." in source
    assert "download_results" in source
    assert "files.download" in source


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


def test_all_code_cells_have_valid_python_syntax() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            ast.parse(cell.source)


def test_generated_cell_ids_are_stable() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    assert [cell.id for cell in notebook.cells] == [
        f"chefbot-{index:02d}" for index in range(len(notebook.cells))
    ]
