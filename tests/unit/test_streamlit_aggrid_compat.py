import ast
import warnings
from pathlib import Path

import pandas as pd
import pyarrow as pa
from st_aggrid import GridOptionsBuilder
from st_aggrid.aggrid_utils import _parse_data_and_grid_options


STLIT_DIR = Path(__file__).resolve().parents[2] / "suzieq" / "gui" / "stlit"
AGGRID_PAGES = ("path.py", "search.py", "xplore.py")


def _page_tree(page):
    return ast.parse((STLIT_DIR / page).read_text(), filename=page)


def _aggrid_calls(page):
    for node in ast.walk(_page_tree(page)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "AgGrid":
            yield node


def test_aggrid_pages_do_not_use_deprecated_update_mode():
    for page in AGGRID_PAGES:
        tree = _page_tree(page)

        imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "st_aggrid"
            for alias in node.names
        ]
        assert "GridUpdateMode" not in imports

        for call in _aggrid_calls(page):
            keywords = {keyword.arg for keyword in call.keywords}
            assert "update_mode" not in keywords


def test_aggrid_pages_do_not_use_deprecated_fit_columns_parameter():
    for page in AGGRID_PAGES:
        for call in _aggrid_calls(page):
            keywords = {keyword.arg for keyword in call.keywords}
            assert "fit_columns_on_grid_load" not in keywords


def test_display_only_grids_disable_update_events():
    for page in ("path.py", "search.py"):
        calls = list(_aggrid_calls(page))
        assert calls
        for call in calls:
            update_on = next(
                (keyword.value for keyword in call.keywords
                 if keyword.arg == "update_on"),
                None,
            )
            assert isinstance(update_on, ast.List)
            assert update_on.elts == []


def test_search_grid_does_not_mutate_results_or_fit_columns(monkeypatch):
    from suzieq.gui.stlit.search import SearchPage
    import suzieq.gui.stlit.search as search

    class Expander:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    aggrid_args = {}

    def fake_aggrid(data, **kwargs):
        if "getRowId" not in kwargs["gridOptions"]:
            data["::auto_unique_id::"] = ["0"] * len(data)
        aggrid_args["data"] = data
        aggrid_args["kwargs"] = kwargs

    monkeypatch.setattr(search, "AgGrid", fake_aggrid)

    df = pd.DataFrame({
        "namespace": ["lab", "lab"],
        "hostname": ["spine01", "spine02"],
        "vlan": [1, 1],
        "::auto_unique_id::": ["0", "1"],
    })

    SearchPage()._draw_aggrid_df(Expander(), df)

    grid_options = aggrid_args["kwargs"]["gridOptions"]
    display_columns = [
        column["field"] for column in grid_options["columnDefs"]
    ]
    row_id_col = next(
        column
        for column in grid_options["columnDefs"]
        if column["field"] == "__sq_row_id__"
    )

    assert "__sq_row_id__" not in df.columns
    assert "::auto_unique_id::" not in aggrid_args["data"].columns
    assert "::auto_unique_id::" not in display_columns
    assert "autoSizeStrategy" not in grid_options
    assert "getRowId" in grid_options
    assert row_id_col["hide"] is True


def test_aggrid_display_helpers_avoid_internal_dataframe_mutation():
    from suzieq.gui.stlit.guiutils import (
        build_aggrid_display_df,
        set_aggrid_id_options,
        strip_aggrid_internal_columns,
    )

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-04-20T10:00:00Z"]),
        "value": [1],
    })
    sliced_df = df.iloc[:1]
    display_df = build_aggrid_display_df(sliced_df)
    grid_options = set_aggrid_id_options(
        GridOptionsBuilder.from_dataframe(display_df).build()
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", pd.errors.SettingWithCopyWarning)
        parsed_df, parsed_options, _ = _parse_data_and_grid_options(
            display_df,
            grid_options,
            {},
            True,
            "auto",
        )

    assert "::auto_unique_id::" not in parsed_df.columns
    assert "::auto_unique_id::" not in display_df.columns
    assert "getRowId" in parsed_options
    assert "__sq_row_id__" not in strip_aggrid_internal_columns(
        parsed_df
    ).columns


def test_aggrid_display_helper_normalizes_mixed_object_columns():
    from suzieq.gui.stlit.guiutils import build_aggrid_display_df

    df = pd.DataFrame({
        "namespace": ["lab", "lab"],
        "bgp": [False, ""],
    })

    display_df = build_aggrid_display_df(df)

    assert df["bgp"].tolist() == [False, ""]
    assert display_df["bgp"].tolist() == ["False", ""]
    pa.Table.from_pandas(display_df)
