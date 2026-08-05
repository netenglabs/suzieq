import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace


GUI_PATH = (
    Path(__file__).resolve().parents[2]
    / "suzieq"
    / "gui"
    / "stlit"
    / "suzieq-gui.py"
)


class GuiSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def load_gui_module():
    spec = importlib.util.spec_from_file_location("suzieq_gui_for_test", GUI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gui_tree():
    return ast.parse(GUI_PATH.read_text(), filename=str(GUI_PATH))


def test_page_selector_uses_streamlit_horizontal_radio():
    tree = _gui_tree()

    page_radio_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "radio"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "Page"
    ]

    assert len(page_radio_calls) == 1
    radio_keywords = {
        keyword.arg: keyword.value
        for keyword in page_radio_calls[0].keywords
    }

    assert isinstance(radio_keywords.get("horizontal"), ast.Constant)
    assert radio_keywords["horizontal"].value is True


def test_leaving_search_clears_search_widget_state(monkeypatch):
    module = load_gui_module()
    state = GuiSessionState(
        page="Search",
        sq_page="Status",
        search="leaf01",
        search_text="leaf01",
    )
    query_params = {}

    monkeypatch.setattr(module, "st", SimpleNamespace(session_state=state))
    monkeypatch.setattr(
        module, "set_query_params",
        lambda **params: query_params.update(params),
    )

    module.main_sync_state()

    assert state.page == "Status"
    assert state.search_text == ""
    assert state.search == ""
    assert query_params == {"page": "Status"}
