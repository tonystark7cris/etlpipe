"""convert — .yxmd XML workflow to Etlpipe YAML converter.

Converts .yxmd visual workflow files into Etlpipe pipeline
YAML files that can be executed with ``etlpipe run``.

CLI usage::

    etlpipe convert my_workflow.yxmd -o my_pipeline.yaml
    etlpipe convert my_workflow.yxmd          # prints to stdout
    etlpipe convert my_workflow.yxmd --dry-run  # preview without writing

Python API::

    from etlpipe.convert import YxmdConverter
    converter = YxmdConverter("my_workflow.yxmd")
    yaml_text = converter.to_yaml()
    converter.save("my_pipeline.yaml")

Legal notice:
    .yxmd files are plain XML owned by the user who created them.
    This converter reads only the file format — it does not use, embed,
    or depend on any proprietary code, SDK, or runtime.
    Etlpipe is a standalone, open-source project and is not affiliated
    with or endorsed by any proprietary software vendor.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("etlpipe.convert")

# ---------------------------------------------------------------------------
# .yxmd plugin → Etlpipe tool mapping
# ---------------------------------------------------------------------------
# Keys are the *short* plugin class name extracted from the fully-qualified
# plugin string, e.g.:
#   "BasePluginsGui.DbFileInput.DbFileInput"  → "DbFileInput"
#
# Values are callables that accept an ElementTree <Node> element and return
# a (tool_str, args_dict, notes_list) triple.
# ---------------------------------------------------------------------------


def _get_config(node_el) -> Any:
    """Return the <Configuration> element for a node (or None)."""
    return node_el.find("./Properties/Configuration")


def _text(el, xpath: str, default: str = "") -> str:
    found = el.find(xpath)
    return (found.text or default).strip() if found is not None and found.text else default


def _attr(el, xpath: str, attr: str, default: str = "") -> str:
    found = el.find(xpath)
    return (found.attrib.get(attr, default) or default).strip() if found is not None else default


# ---- Individual tool mappers -----------------------------------------------


def _map_input(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    file_path = ""
    notes = []
    if cfg is not None:
        file_path = _text(cfg, "./File")
        if not file_path:
            file_path = _text(cfg, "./Alias")
    if not file_path:
        file_path = "TODO_set_input_path.csv"
        notes.append("⚠ Could not read file path — please set 'path' manually.")
    return "InOut.input_data", {"path": file_path}, notes


def _map_output(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    file_path = ""
    notes = []
    if cfg is not None:
        file_path = _text(cfg, "./File")
        if not file_path:
            file_path = _text(cfg, "./Alias")
    if not file_path:
        file_path = "TODO_set_output_path.csv"
        notes.append("⚠ Could not read file path — please set 'path' manually.")
    return "InOut.output_data", {"path": file_path}, notes


def _map_filter(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    condition = ""
    if cfg is not None:
        expr_el = cfg.find("./Expression")
        if expr_el is not None and expr_el.text:
            # The workflow uses a specialized formula expression; perform best-effort conversion
            condition = _translate_yxmd_expression(expr_el.text.strip())
        if not condition:
            condition = _text(cfg, "./Expression")
    if not condition:
        condition = "TODO_set_filter_condition"
        notes.append("⚠ Filter condition could not be parsed — set 'condition' manually.")
    return "Preparation.filter", {"condition": condition}, notes


def _map_sort(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    columns: list[str] = []
    ascending: list[bool] = []
    if cfg is not None:
        for sf in cfg.findall("./SortInfo/Field"):
            col = sf.attrib.get("field", "")
            order = sf.attrib.get("order", "Ascending")
            if col:
                columns.append(col)
                ascending.append(order.lower() != "descending")
    if not columns:
        notes.append("⚠ Sort columns could not be detected — set 'columns' manually.")
        return "Preparation.sort", {"columns": ["TODO_column"], "ascending": True}, notes
    return (
        "Preparation.sort",
        {
            "columns": columns if len(columns) > 1 else columns[0],
            "ascending": ascending if len(ascending) > 1 else ascending[0],
        },
        notes,
    )


def _map_select(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    keep_cols: list[str] = []
    renames: dict[str, str] = {}
    dtypes: dict[str, str] = {}

    if cfg is not None:
        for sf in cfg.findall("./SelectFields/SelectField"):
            selected = sf.attrib.get("selected", "True")
            if selected.lower() == "false":
                continue
            original = sf.attrib.get("field", "")
            renamed = sf.attrib.get("rename", "")
            dtype = sf.attrib.get("type", "")
            if original:
                keep_cols.append(renamed if renamed else original)
                if renamed and renamed != original:
                    renames[original] = renamed
                if dtype:
                    target_col = renamed if renamed else original
                    mapped_type = _map_yxmd_type(dtype)
                    if mapped_type:
                        dtypes[target_col] = mapped_type

    args: dict[str, Any] = {}
    if keep_cols:
        args["columns"] = keep_cols
    if renames:
        args["renames"] = renames
    if dtypes:
        args["dtypes"] = dtypes
    if not args:
        notes.append("⚠ Select columns could not be detected — configure manually.")

    return "Preparation.select", args, notes


def _map_formula(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    # Formula nodes can compute multiple fields — we emit one step per field
    # and return only the last one as the primary step (earlier ones are
    # stored as sub-steps which the caller handles by noting them in comments).
    formulas = []
    if cfg is not None:
        for ff in cfg.findall("./FormulaFields/FormulaField"):
            col = ff.attrib.get("field", "")
            expr = ff.attrib.get("expression", "")
            if col and expr:
                formulas.append((col, _translate_yxmd_expression(expr)))

    if not formulas:
        notes.append("⚠ Formula expression not detected — configure 'column' and 'expression' manually.")
        return "Preparation.formula", {"column": "TODO_column", "expression": "TODO_expression"}, notes

    if len(formulas) > 1:
        notes.append(
            f"ℹ This tool computes {len(formulas)} fields. Only the last is shown; "
            "chain additional Preparation.formula steps for the others: " + str([f[0] for f in formulas[:-1]])
        )

    last_col, last_expr = formulas[-1]
    return "Preparation.formula", {"column": last_col, "expression": last_expr}, notes


def _map_summarize(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    group_by: list[str] = []
    aggregations: dict[str, str] = {}
    _AGG_MAP = {
        "Sum": "sum",
        "Avg": "mean",
        "Min": "min",
        "Max": "max",
        "Count": "count",
        "First": "first",
        "Last": "last",
        "CountNull": "count",
        "StdDev": "std",
        "Median": "median",
    }
    if cfg is not None:
        for sf in cfg.findall("./SummarizeFields/SummarizeField"):
            action = sf.attrib.get("action", "")
            col = sf.attrib.get("field", "")
            if not col:
                continue
            if action == "GroupBy":
                group_by.append(col)
            elif action in _AGG_MAP:
                aggregations[col] = _AGG_MAP[action]
            else:
                aggregations[col] = action.lower()
                notes.append(f"⚠ Unmapped aggregation '{action}' on '{col}' — verify manually.")

    args: dict[str, Any] = {}
    if group_by:
        args["group_by"] = group_by if len(group_by) > 1 else group_by[0]
    if aggregations:
        args["aggregations"] = aggregations
    return "Transform.summarize", args, notes


def _map_join(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    join_keys: list[str] = []
    if cfg is not None:
        for jf in cfg.findall("./JoinInfo/Field"):
            col = jf.attrib.get("field", "")
            if col:
                join_keys.append(col)
    args: dict[str, Any] = {}
    if join_keys:
        args["on"] = join_keys if len(join_keys) > 1 else join_keys[0]
    else:
        notes.append("⚠ Join key columns not detected — set 'on', 'left_on', or 'right_on' manually.")
    notes.append(
        "ℹ Join.join returns (left_unjoined, joined, right_unjoined). Reference the joined anchor with '<step_id>.1'."
    )
    return "Join.join", args, notes


def _map_union(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    mode = "name"
    if cfg is not None:
        mode_attr = cfg.attrib.get("mode", "Auto")
        if "position" in mode_attr.lower():
            mode = "position"
    notes.append(
        "ℹ Union.union accepts *dfs as positional args. "
        "Adjust the 'inputs' section to include all input step references."
    )
    return "Join.union", {"by": mode}, notes


def _map_unique(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    cols: list[str] = []
    if cfg is not None:
        for f in cfg.findall("./UniqueFields/Field"):
            col = f.attrib.get("field", "")
            if col:
                cols.append(col)
    if not cols:
        notes.append("⚠ Unique columns not detected — set 'columns' manually.")
        return "Preparation.unique", {"columns": ["TODO_column"]}, notes
    return "Preparation.unique", {"columns": cols if len(cols) > 1 else cols[0]}, notes


def _map_sample(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    if cfg is not None:
        n_str = _text(cfg, "./N")
        if n_str.isdigit():
            return "Preparation.sample", {"n": int(n_str)}, notes
        pct_str = _text(cfg, "./Percent")
        if pct_str:
            try:
                return "Preparation.sample", {"pct": float(pct_str) / 100.0}, notes
            except ValueError:
                pass
    notes.append("⚠ Sample size could not be detected — set 'n' or 'pct' manually.")
    return "Preparation.sample", {"n": 1000}, notes


def _map_record_id(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    args: dict[str, Any] = {}
    if cfg is not None:
        col = _text(cfg, "./FieldName")
        if col:
            args["column_name"] = col
        start_str = _text(cfg, "./StartValue")
        if start_str:
            with contextlib.suppress(ValueError):
                args["start"] = int(start_str)
    return "Preparation.record_id", args, []


def _map_data_cleansing(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    args: dict[str, Any] = {}
    notes: list[str] = []
    if cfg is not None:
        null_rows = _text(cfg, "./NullRows")
        if null_rows.lower() == "true":
            args["remove_null_rows"] = True
        whitespace = _text(cfg, "./Whitespace")
        if whitespace.lower() == "false":
            args["strip_whitespace"] = False
        case = _text(cfg, "./Case")
        if case.lower() == "lower":
            args["modify_case"] = "lower"
        elif case.lower() == "upper":
            args["modify_case"] = "upper"
        elif case.lower() == "title":
            args["modify_case"] = "title"
    return "Preparation.data_cleansing", args, notes


def _map_running_total(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    args: dict[str, Any] = {}
    if cfg is not None:
        col = _text(cfg, "./RunningField")
        if col:
            args["column"] = col
        grp_fields = [f.attrib.get("field", "") for f in cfg.findall("./GroupByFields/Field") if f.attrib.get("field")]
        if grp_fields:
            args["group_by"] = grp_fields if len(grp_fields) > 1 else grp_fields[0]
    if "column" not in args:
        args["column"] = "TODO_column"
        notes.append("⚠ Running total column not detected — set 'column' manually.")
    return "Transform.running_total", args, notes


def _map_cross_tab(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    args: dict[str, Any] = {
        "group_by": "TODO_group_by",
        "pivot_col": "TODO_pivot_col",
        "value_col": "TODO_value_col",
    }
    if cfg is not None:
        grp = _text(cfg, "./GroupFields/Field")
        if grp:
            args["group_by"] = grp
        header = _text(cfg, "./HeaderField")
        if header:
            args["pivot_col"] = header
        data = _text(cfg, "./DataField")
        if data:
            args["value_col"] = data
        agg = _text(cfg, "./Method")
        if agg:
            args["agg"] = agg.lower()
    notes.append("⚠ Verify cross_tab args match your workflow's configuration.")
    return "Transform.cross_tab", args, notes


def _map_transpose(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    key_cols: list[str] = []
    data_cols: list[str] = []
    if cfg is not None:
        for f in cfg.findall("./KeyFields/Field"):
            col = f.attrib.get("field", "")
            if col:
                key_cols.append(col)
        for f in cfg.findall("./DataFields/Field"):
            col = f.attrib.get("field", "")
            if col:
                data_cols.append(col)
    args: dict[str, Any] = {"key_columns": key_cols if key_cols else "TODO_key_column"}
    if data_cols:
        args["data_columns"] = data_cols
    return "Transform.transpose", args, notes


def _map_text_input(node_el) -> tuple[str, dict, list[str]]:
    notes = [
        "ℹ Text Input inline data is not extracted; replace with InOut.input_data or InOut.text_input with inline data."
    ]
    return "InOut.text_input", {"data": {"TODO_column": ["TODO_value"]}}, notes


def _map_browse(node_el) -> tuple[str, dict, list[str]]:
    return "InOut.browse", {}, []


def _map_append_fields(node_el) -> tuple[str, dict, list[str]]:
    notes = ["ℹ Join.append_fields is a cross join. Set 'left' and 'right' inputs referencing upstream step IDs."]
    return "Join.append_fields", {}, notes


def _map_fuzzy_match(node_el) -> tuple[str, dict, list[str]]:
    notes = ["⚠ Set 'left_on' and 'right_on' column names manually."]
    return "Join.fuzzy_match", {"left_on": "TODO_left_col", "right_on": "TODO_right_col"}, notes


def _map_imputation(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    args: dict[str, Any] = {"columns": "TODO_column", "method": "mean"}
    if cfg is not None:
        method = _text(cfg, "./Method")
        if method:
            args["method"] = method.lower()
    notes.append("⚠ Set 'columns' to the column(s) to impute.")
    return "Preparation.imputation", args, notes


def _map_tile(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    args: dict[str, Any] = {"column": "TODO_column", "n_tiles": 4}
    if cfg is not None:
        n = _text(cfg, "./NumTiles")
        if n.isdigit():
            args["n_tiles"] = int(n)
        col = _text(cfg, "./TileField")
        if col:
            args["column"] = col
        method = _text(cfg, "./Method")
        if method:
            args["method"] = "equal_range" if "range" in method.lower() else "equal_records"
    return "Preparation.tile", args, notes


def _map_generate_rows(node_el) -> tuple[str, dict, list[str]]:
    cfg = _get_config(node_el)
    notes = []
    count = 10
    if cfg is not None:
        n_str = _text(cfg, "./NumRows")
        if n_str.isdigit():
            count = int(n_str)
    notes.append("ℹ Generate Rows: provide an 'expression' callable if needed.")
    return "Preparation.generate_rows", {"count": count}, notes


# ---------------------------------------------------------------------------
# Plugin → mapper dispatch table
# ---------------------------------------------------------------------------
_PLUGIN_MAP: dict[str, callable] = {
    # In/Out
    "DbFileInput": _map_input,
    "Select": _map_select,
    "TextInput": _map_text_input,
    "DbFileOutput": _map_output,
    "Browse": _map_browse,
    "DirectoryV2": lambda n: ("InOut.directory", {"path": "TODO_directory_path"}, ["⚠ Set 'path' manually."]),
    # Preparation
    "Filter": _map_filter,
    "Sort": _map_sort,
    "Formula": _map_formula,
    "MultiFieldFormula": lambda n: (
        "Preparation.multi_field_formula",
        {"columns": ["TODO_column"], "expression": "TODO_expression"},
        ["⚠ Set 'columns' and 'expression' manually."],
    ),
    "MultiRowFormula": lambda n: (
        "Preparation.multi_row_formula",
        {"column": "TODO_column", "expression": "TODO_expression"},
        ["⚠ Set 'column' and 'expression' manually."],
    ),
    "Unique": _map_unique,
    "Sample": _map_sample,
    "RecordID": _map_record_id,
    "DataCleansing": _map_data_cleansing,
    "Imputation": _map_imputation,
    "Tile": _map_tile,
    "GenerateRows": _map_generate_rows,
    "AutoField": lambda n: ("Preparation.auto_field", {}, []),
    "DateFilter": lambda n: (
        "Preparation.date_filter",
        {"column": "TODO_date_column"},
        ["⚠ Set 'column', 'start_date', 'end_date' manually."],
    ),
    "Rank": lambda n: ("Preparation.rank", {"column": "TODO_column"}, ["⚠ Set 'column' manually."]),
    "OversampleField": lambda n: (
        "Preparation.oversample_field",
        {"column": "TODO_column", "value": "TODO_value"},
        ["⚠ Set 'column' and 'value' manually."],
    ),
    # Join / Blend
    "Join": _map_join,
    "Union": _map_union,
    "AppendFields": _map_append_fields,
    "FindReplace": lambda n: (
        "Join.find_replace",
        {"find_col": "TODO_find_col", "replace_col": "TODO_replace_col"},
        ["⚠ Set 'find_col' and 'replace_col' manually."],
    ),
    "FuzzyMatch": _map_fuzzy_match,
    "MakeGroup": lambda n: (
        "Join.make_group",
        {"key1": "TODO_key1", "key2": "TODO_key2"},
        ["⚠ Set 'key1' and 'key2' manually."],
    ),
    # Transform
    "Summarize": _map_summarize,
    "Transpose": _map_transpose,
    "CrossTab": _map_cross_tab,
    "RunningTotal": _map_running_total,
    "CountRecords": lambda n: ("Transform.count_records", {}, []),
    # Parse
    "DateTime": lambda n: ("Parse.date_time", {"column": "TODO_column"}, ["⚠ Set 'column' manually."]),
    "RegExTool": lambda n: (
        "Parse.regex_match",
        {"column": "TODO_column", "pattern": "TODO_pattern"},
        ["⚠ Set 'column' and 'pattern' manually."],
    ),
    "TextToColumns": lambda n: (
        "Parse.text_to_columns",
        {"column": "TODO_column", "delimiter": ","},
        ["⚠ Set 'column' and 'delimiter' manually."],
    ),
    "XmlParse": lambda n: (
        "Parse.xml_parse",
        {"column": "TODO_column", "xpath": "TODO_xpath"},
        ["⚠ Set 'column' and 'xpath' manually."],
    ),
}


def _extract_plugin_short_name(plugin_str: str) -> str:
    """Extract the short class name from a plugin string.

    e.g. 'BasePluginsGui.DbFileInput.DbFileInput' → 'DbFileInput'
    """
    parts = plugin_str.split(".")
    short = parts[-1] if parts else plugin_str
    # Dynamically strip any leading vendor prefix before standard tool names
    short = re.sub(
        r"^[A-Z][a-z]+(?=(?:Select|Input|Output|Filter|Formula|Sort|Join|Union|Summarize|Transpose))", "", short
    )
    return short


# ---------------------------------------------------------------------------
# Expression translator (best-effort .yxmd formula → pandas query)
# ---------------------------------------------------------------------------


def _translate_yxmd_expression(expr: str) -> str:
    """Attempt a best-effort translation of a .yxmd formula expression.

    Handles the most common patterns. Complex specialized functions
    are left as-is with a TODO comment so the user knows to review them.
    """
    result = expr

    # Boolean literals
    result = re.sub(r"\bTrue\b", "True", result, flags=re.IGNORECASE)
    result = re.sub(r"\bFalse\b", "False", result, flags=re.IGNORECASE)
    result = re.sub(r"\bNull\(\)", "None", result)

    # Logical operators
    result = re.sub(r"\bAND\b", "and", result, flags=re.IGNORECASE)
    result = re.sub(r"\bOR\b", "or", result, flags=re.IGNORECASE)
    result = re.sub(r"\bNOT\b", "not", result, flags=re.IGNORECASE)

    # Comparison operators
    result = result.replace("<>", "!=")
    result = result.replace("==", "==")

    # CONTAINS([Col], "val") → Col.str.contains("val")
    result = re.sub(r"CONTAINS\(\[(\w+)\],\s*\"([^\"]*)\"\)", r'\1.str.contains("\2")', result, flags=re.IGNORECASE)

    # STARTSWITH([Col], "val") → Col.str.startswith("val")
    result = re.sub(r"STARTSWITH\(\[(\w+)\],\s*\"([^\"]*)\"\)", r'\1.str.startswith("\2")', result, flags=re.IGNORECASE)

    # ISNULL([Col]) → Col.isnull()
    result = re.sub(r"ISNULL\(\[(\w+)\]\)", r"\1.isnull()", result, flags=re.IGNORECASE)

    # ISNOTNULL([Col]) → Col.notna()
    result = re.sub(r"ISNOTNULL\(\[(\w+)\]\)", r"\1.notna()", result, flags=re.IGNORECASE)

    # [FieldName] → FieldName  (strip square brackets)
    result = re.sub(r"\[(\w+)\]", r"\1", result)

    return result


# ---------------------------------------------------------------------------
# Type mapper
# ---------------------------------------------------------------------------


def _map_yxmd_type(yxmd_type: str) -> str | None:
    _TYPE_MAP = {
        "String": "str",
        "V_String": "str",
        "WString": "str",
        "V_WString": "str",
        "Int16": "int16",
        "Int32": "int32",
        "Int64": "int64",
        "Float": "float32",
        "Double": "float64",
        "Bool": "bool",
        "Date": "datetime64[ns]",
        "DateTime": "datetime64[ns]",
        "Time": "str",
        "Blob": None,
        "SpatialObj": None,
    }
    return _TYPE_MAP.get(yxmd_type)


# ---------------------------------------------------------------------------
# Main converter class
# ---------------------------------------------------------------------------


class YxmdConverter:
    """Convert a .yxmd XML workflow file to a Etlpipe YAML pipeline.

    Args:
        source: Path to the .yxmd file.

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If the file cannot be parsed as valid workflow XML.
    """

    def __init__(self, source: str | Path) -> None:
        self.source = Path(source)
        if not self.source.exists():
            raise FileNotFoundError(f"Source file not found: {self.source}")
        self._nodes: dict[int, dict[str, Any]] = {}  # tool_id → node info
        self._connections: list[tuple[int, str, int, str]] = []  # (from_id, from_port, to_id, to_port)
        self._warnings: list[str] = []
        self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        """Parse the .yxmd XML into internal node/connection structures."""
        try:
            import defusedxml.ElementTree as ET
        except ImportError:
            raise ImportError(
                "defusedxml is required for safe XML parsing of .yxmd files. Install it with: pip install defusedxml"
            ) from None

        try:
            tree = ET.parse(str(self.source))
        except Exception as exc:
            raise ValueError(f"Failed to parse {self.source} as XML: {exc}") from exc

        root = tree.getroot()
        root_tag = root.tag
        if root.find(".//Node") is None and root.find(".//Nodes") is None:
            raise ValueError(f"Expected visual workflow XML document, got root tag <{root_tag}>")

        # Parse nodes
        for node_el in root.findall(".//Node"):
            tool_id_str = node_el.attrib.get("ToolID", "")
            if not tool_id_str.isdigit():
                continue
            tool_id = int(tool_id_str)

            plugin = _attr(node_el, "./GuiSettings", "Plugin", default="Unknown")
            short_name = _extract_plugin_short_name(plugin)

            # Attempt position for informational ordering
            x = float(_attr(node_el, "./GuiSettings/Position", "x", "0") or 0)
            y = float(_attr(node_el, "./GuiSettings/Position", "y", "0") or 0)

            annotation = _text(node_el, "./Properties/Annotation/Name")

            self._nodes[tool_id] = {
                "tool_id": tool_id,
                "plugin": plugin,
                "short_name": short_name,
                "annotation": annotation,
                "x": x,
                "y": y,
                "el": node_el,
            }

        # Parse connections
        for conn_el in root.findall(".//Connection"):
            origin_el = conn_el.find("./Origin")
            dest_el = conn_el.find("./Destination")
            if origin_el is None or dest_el is None:
                continue
            try:
                from_id = int(origin_el.attrib.get("ToolID", -1))
                to_id = int(dest_el.attrib.get("ToolID", -1))
            except (ValueError, TypeError):
                continue
            from_port = origin_el.attrib.get("Connection", "Output")
            to_port = dest_el.attrib.get("Connection", "Input")
            if from_id >= 0 and to_id >= 0:
                self._connections.append((from_id, from_port, to_id, to_port))

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def _topological_order(self) -> list[int]:
        """Return node IDs in topological (execution) order using Kahn's algorithm."""
        in_degree: dict[int, int] = defaultdict(int)
        adjacency: dict[int, list[int]] = defaultdict(list)

        for nid in self._nodes:
            in_degree[nid] = in_degree.get(nid, 0)

        for from_id, _, to_id, _ in self._connections:
            if from_id in self._nodes and to_id in self._nodes:
                adjacency[from_id].append(to_id)
                in_degree[to_id] += 1

        # Seed with nodes that have no incoming edges, sorted by x-position
        # so left-to-right canvas order is preserved where possible.
        queue: deque[int] = deque(
            sorted(
                [nid for nid in self._nodes if in_degree[nid] == 0],
                key=lambda nid: (self._nodes[nid]["x"], self._nodes[nid]["y"]),
            )
        )
        order: list[int] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbor in sorted(adjacency[nid]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Append any remaining nodes (cycles / disconnected)
        for nid in self._nodes:
            if nid not in order:
                order.append(nid)
                self._warnings.append(
                    f"⚠ Tool {nid} ({self._nodes[nid]['short_name']}) is in a cycle or disconnected — placed at end."
                )
        return order

    # ------------------------------------------------------------------
    # Step ID generation
    # ------------------------------------------------------------------

    def _make_step_id(self, tool_id: int) -> str:
        """Generate a clean YAML step ID for a tool."""
        node = self._nodes[tool_id]
        annotation = node["annotation"]
        short = node["short_name"].lower()

        if annotation:
            # Normalise annotation to snake_case
            clean = re.sub(r"[^a-zA-Z0-9 _]", "", annotation).strip().lower()
            clean = re.sub(r"\s+", "_", clean)
            if clean:
                return f"{clean}_{tool_id}"

        return f"{short}_{tool_id}"

    # ------------------------------------------------------------------
    # YAML generation
    # ------------------------------------------------------------------

    def _build_pipeline_dict(self) -> dict[str, Any]:
        """Build the Etlpipe pipeline dict from parsed nodes."""
        order = self._topological_order()

        # Map tool_id → step_id for building input references
        id_to_step: dict[int, str] = {tid: self._make_step_id(tid) for tid in self._nodes}

        # Track which step_ids are upstream producers for each node
        # to_id → [(from_step_id, to_port)]
        upstream: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
        for from_id, from_port, to_id, to_port in self._connections:
            if from_id in self._nodes and to_id in self._nodes:
                upstream[to_id].append((id_to_step[from_id], from_port, to_port))

        steps = []
        workflow_name = self.source.stem.replace("_", " ").title()
        all_notes: list[str] = list(self._warnings)

        for tool_id in order:
            node = self._nodes[tool_id]
            short_name = node["short_name"]
            step_id = id_to_step[tool_id]

            # Map plugin to Etlpipe tool
            if short_name in _PLUGIN_MAP:
                mapper = _PLUGIN_MAP[short_name]
                try:
                    tool_str, args, notes = mapper(node["el"])
                except Exception as exc:
                    tool_str = "TODO_tool"
                    args = {}
                    notes = [f"⚠ Mapper error for {short_name}: {exc}"]
            else:
                tool_str = f"TODO_{node['short_name']}"
                args = {"_plugin": node["plugin"]}
                notes = [
                    f"⚠ No mapping for plugin '{node['plugin']}'. Replace with equivalent Etlpipe tool or custom logic."
                ]
                self._warnings.append(f"Unmapped plugin '{short_name}' (ToolID {tool_id}) — manual step required.")

            # Build inputs section from upstream connections
            inputs: dict[str, str] = {}
            ups = upstream.get(tool_id, [])
            if ups:
                # Determine default parameter names based on tool
                if len(ups) == 1:
                    from_step, from_port, to_port = ups[0]
                    ref = _make_output_ref(from_step, from_port)
                    param = _infer_input_param(tool_str, to_port, index=0)
                    inputs[param] = ref
                else:
                    for i, (from_step, from_port, to_port) in enumerate(ups):
                        ref = _make_output_ref(from_step, from_port)
                        param = _infer_input_param(tool_str, to_port, index=i)
                        inputs[param] = ref

            # Build the step dict (YAML-safe)
            step: dict[str, Any] = {"id": step_id, "tool": tool_str}
            if inputs:
                step["inputs"] = inputs
            if args:
                step["args"] = args
            if notes:
                # Store notes so we can inject them as YAML comments later
                step["_notes"] = notes
                all_notes.extend(notes)

            steps.append(step)

        return {
            "_name": workflow_name,
            "_steps": steps,
            "_all_notes": all_notes,
        }

    def to_yaml(self) -> str:
        """Convert the workflow to a Etlpipe YAML string.

        Returns:
            A YAML string ready to pass to ``etlpipe run`` or save to disk.
        """
        data = self._build_pipeline_dict()
        steps = data["_steps"]
        workflow_name = data["_name"]

        lines: list[str] = [
            "# Etlpipe pipeline — auto-generated from .yxmd visual workflow",
            f"# Source: {self.source.name}",
            "# Generator: etlpipe convert (standalone XML workflow converter)",
            "#",
            "# ⚠  Review all TODO_ placeholders before running.",
            "# ⚠  Steps marked with '# NOTE:' may need manual adjustment.",
            "",
            f"name: {_yaml_str(workflow_name)}",
            "steps:",
        ]

        for step in steps:
            notes = step.pop("_notes", [])
            for note in notes:
                lines.append(f"  # NOTE: {note}")

            # Serialize step as YAML, then convert to a list-item block:
            # The first key becomes "  - key: value", the rest "    key: value"
            step_yaml = yaml.dump(
                step,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
            )
            step_lines = step_yaml.splitlines()
            for i, line in enumerate(step_lines):
                if i == 0:
                    # First line gets the list marker
                    lines.append(f"  - {line}")
                else:
                    # Subsequent lines are indented under the list item
                    lines.append(f"    {line}")
            lines.append("")

        return "\n".join(lines)

    def save(self, output_path: str | Path) -> None:
        """Write the converted YAML to a file.

        Args:
            output_path: Destination path for the Etlpipe YAML file.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        yaml_text = self.to_yaml()
        out.write_text(yaml_text, encoding="utf-8")
        logger.info("Saved converted pipeline to: %s", out)

    @property
    def warnings(self) -> list[str]:
        """Return a list of conversion warnings (unmapped tools, missing config, etc.)."""
        return list(self._warnings)

    @property
    def node_count(self) -> int:
        """Number of tool nodes found in the workflow."""
        return len(self._nodes)

    @property
    def coverage(self) -> float:
        """Fraction of tools (0.0–1.0) that have a known Etlpipe mapping."""
        if not self._nodes:
            return 1.0
        mapped = sum(1 for n in self._nodes.values() if n["short_name"] in _PLUGIN_MAP)
        return mapped / len(self._nodes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_output_ref(step_id: str, from_port: str) -> str:
    """Build a pipeline state reference string.

    Visual workflow output anchors:
    - Standard Output / Output / True / T → index 0 (or no suffix if single output)
    - False / F → index 1
    - Left / L → index 0
    - Joined / J → index 1
    - Right / R → index 2
    - Unique / U → index 0
    - Duplicate / D → index 1
    """
    _PORT_INDEX = {
        "T": "0",
        "F": "1",  # Filter
        "L": "0",
        "J": "1",
        "R": "2",  # Join
        "U": "0",
        "D": "1",  # Unique
        "1": "0",
        "2": "1",  # numeric anchors
    }
    idx = _PORT_INDEX.get(from_port.upper())
    if idx is not None:
        return f"{step_id}.{idx}"
    return step_id


def _infer_input_param(tool_str: str, to_port: str, index: int) -> str:
    """Guess the best parameter name for an input based on tool and port."""
    if "join" in tool_str.lower():
        return "left" if index == 0 else "right"
    if "union" in tool_str.lower():
        return f"df{index}"
    if "append_fields" in tool_str.lower():
        return "left" if index == 0 else "right"
    if "find_replace" in tool_str.lower():
        return "df" if index == 0 else "find_df"
    return "df"


def _yaml_str(s: str) -> str:
    """Wrap a string in double quotes for YAML safety."""
    return f'"{s}"'


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def convert_cli_main(args_list: list[str] | None = None) -> None:
    """CLI entrypoint for ``etlpipe-convert``."""
    parser = argparse.ArgumentParser(
        prog="etlpipe-convert",
        description="Convert a .yxmd workflow file to a Etlpipe pipeline YAML.",
    )
    parser.add_argument("source", type=str, help="Path to the .yxmd workflow file.")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output YAML path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the converted YAML without writing to disk.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a conversion summary (node count, coverage, warnings).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    try:
        converter = YxmdConverter(args.source)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    yaml_text = converter.to_yaml()

    if args.summary or args.dry_run:
        covered = int(converter.coverage * 100)
        print(f"\n{'─' * 50}", file=sys.stderr)
        print(f"  Source    : {converter.source.name}", file=sys.stderr)
        print(f"  Nodes     : {converter.node_count}", file=sys.stderr)
        print(f"  Coverage  : {covered}% tools mapped to Etlpipe", file=sys.stderr)
        if converter.warnings:
            print(f"  Warnings  : {len(converter.warnings)}", file=sys.stderr)
            for w in converter.warnings:
                print(f"    • {w}", file=sys.stderr)
        print(f"{'─' * 50}\n", file=sys.stderr)

    if args.dry_run:
        print(yaml_text)
        return

    if args.output:
        converter.save(args.output)
        covered = int(converter.coverage * 100)
        print(
            f"✅ Converted '{args.source}' → '{args.output}' ({converter.node_count} tools, {covered}% mapped)",
            file=sys.stderr,
        )
        if converter.warnings:
            print(
                f"⚠  {len(converter.warnings)} tools need manual review. Search the output for 'TODO_'.",
                file=sys.stderr,
            )
    else:
        print(yaml_text)
