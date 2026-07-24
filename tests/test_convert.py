"""Tests for etlpipe.convert — .yxmd → Etlpipe YAML converter."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from etlpipe.convert import (
    YxmdConverter,
    _extract_plugin_short_name,
    _make_output_ref,
    _translate_yxmd_expression,
)

# ── Path to the shared fixture ──────────────────────────────────────────────
FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_YXMD = FIXTURES / "sample_workflow.yxmd"


# ============================================================================
# Helper utilities
# ============================================================================


class TestExtractPluginShortName:
    def test_three_part_plugin_string(self):
        assert _extract_plugin_short_name("BasePluginsGui.DbFileInput.DbFileInput") == "DbFileInput"

    def test_two_part_plugin_string(self):
        assert _extract_plugin_short_name("LockIn.Filter") == "Filter"

    def test_single_token(self):
        assert _extract_plugin_short_name("Summarize") == "Summarize"

    def test_empty_string(self):
        assert _extract_plugin_short_name("") == ""


class TestMakeOutputRef:
    def test_standard_output_no_suffix(self):
        assert _make_output_ref("step_a", "Output") == "step_a"

    def test_filter_true_anchor(self):
        assert _make_output_ref("filter_1", "T") == "filter_1.0"

    def test_filter_false_anchor(self):
        assert _make_output_ref("filter_1", "F") == "filter_1.1"

    def test_join_left_anchor(self):
        assert _make_output_ref("join_1", "L") == "join_1.0"

    def test_join_joined_anchor(self):
        assert _make_output_ref("join_1", "J") == "join_1.1"

    def test_join_right_anchor(self):
        assert _make_output_ref("join_1", "R") == "join_1.2"

    def test_unique_unique_anchor(self):
        assert _make_output_ref("unique_1", "U") == "unique_1.0"

    def test_unique_duplicate_anchor(self):
        assert _make_output_ref("unique_1", "D") == "unique_1.1"

    def test_unknown_port_no_suffix(self):
        assert _make_output_ref("step_x", "Weird") == "step_x"


class TestTranslateYxmdExpression:
    def test_field_brackets_removed(self):
        result = _translate_yxmd_expression("[Revenue] > 1000")
        assert "Revenue > 1000" in result
        assert "[" not in result

    def test_and_lowercased(self):
        result = _translate_yxmd_expression("[A] > 0 AND [B] < 10")
        assert " and " in result

    def test_or_lowercased(self):
        result = _translate_yxmd_expression("[X] == 1 OR [Y] == 2")
        assert " or " in result

    def test_not_equals_converted(self):
        result = _translate_yxmd_expression('[Status] <> "Active"')
        assert "!=" in result
        assert "<>" not in result

    def test_isnull_converted(self):
        result = _translate_yxmd_expression("ISNULL([Email])")
        assert "Email.isnull()" in result

    def test_contains_converted(self):
        result = _translate_yxmd_expression('CONTAINS([Name], "Smith")')
        assert 'Name.str.contains("Smith")' in result

    def test_null_function_converted(self):
        result = _translate_yxmd_expression("Null()")
        assert "None" in result


# ============================================================================
# YxmdConverter — core functionality
# ============================================================================


class TestYxmdConverterInit:
    def test_loads_sample_workflow(self):
        c = YxmdConverter(SAMPLE_YXMD)
        assert c.node_count > 0

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            YxmdConverter("nonexistent_file.yxmd")

    def test_invalid_xml_raises(self, tmp_path):
        bad = tmp_path / "bad.yxmd"
        bad.write_text("this is not xml!!!", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to parse"):
            YxmdConverter(bad)


class TestYxmdConverterNodeCount:
    def test_sample_has_seven_nodes(self):
        c = YxmdConverter(SAMPLE_YXMD)
        assert c.node_count == 7


class TestYxmdConverterCoverage:
    def test_coverage_between_0_and_1(self):
        c = YxmdConverter(SAMPLE_YXMD)
        assert 0.0 <= c.coverage <= 1.0

    def test_sample_workflow_fully_covered(self):
        """All tools in the fixture have known Etlpipe mappings."""
        c = YxmdConverter(SAMPLE_YXMD)
        assert c.coverage == 1.0


class TestYxmdConverterToYaml:
    """Test that to_yaml() produces valid, correct YAML."""

    @pytest.fixture(scope="class")
    @classmethod
    def yaml_text(cls, request):
        text = YxmdConverter(SAMPLE_YXMD).to_yaml()
        request.cls._yaml_text = text
        return text

    @pytest.fixture(scope="class")
    @classmethod
    def parsed_steps(cls, request, yaml_text):
        """Parse just the steps from the output (strip comment header)."""
        content_lines = [ln for ln in yaml_text.splitlines() if not ln.startswith("#")]
        parsed = yaml.safe_load("\n".join(content_lines))
        request.cls._parsed = parsed
        return parsed

    def test_produces_non_empty_string(self, yaml_text):
        assert len(yaml_text) > 100

    def test_contains_name_key(self, yaml_text):
        assert "name:" in yaml_text

    def test_contains_steps_key(self, yaml_text):
        assert "steps:" in yaml_text

    def test_has_legal_disclaimer_comment(self, yaml_text):
        assert "standalone XML workflow converter" in yaml_text

    def test_has_todo_warning_comment(self, yaml_text):
        assert "TODO_" in yaml_text or "Review all TODO_" in yaml_text

    def test_parsed_steps_is_list(self, parsed_steps):
        assert isinstance(parsed_steps.get("steps"), list)

    def test_all_steps_have_id(self, parsed_steps):
        for step in parsed_steps["steps"]:
            assert "id" in step, f"Step missing 'id': {step}"

    def test_all_steps_have_tool(self, parsed_steps):
        for step in parsed_steps["steps"]:
            assert "tool" in step, f"Step missing 'tool': {step}"

    def test_input_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "InOut.input_data" in tools

    def test_output_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "InOut.output_data" in tools

    def test_filter_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "Preparation.filter" in tools

    def test_summarize_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "Transform.summarize" in tools

    def test_sort_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "Preparation.sort" in tools

    def test_formula_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "Preparation.formula" in tools

    def test_select_tool_mapped(self, parsed_steps):
        tools = [s["tool"] for s in parsed_steps["steps"]]
        assert "Preparation.select" in tools

    def test_input_step_has_path_arg(self, parsed_steps):
        input_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "InOut.input_data"), None)
        assert input_step is not None
        assert "path" in input_step.get("args", {})
        assert input_step["args"]["path"] == "sales_data.csv"

    def test_output_step_has_path_arg(self, parsed_steps):
        output_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "InOut.output_data"), None)
        assert output_step is not None
        assert "path" in output_step.get("args", {})
        assert output_step["args"]["path"] == "regional_summary.csv"

    def test_filter_condition_parsed(self, parsed_steps):
        filter_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.filter"), None)
        assert filter_step is not None
        condition = filter_step.get("args", {}).get("condition", "")
        assert "Revenue" in condition
        assert "1000" in condition

    def test_sort_column_parsed(self, parsed_steps):
        sort_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.sort"), None)
        assert sort_step is not None
        args = sort_step.get("args", {})
        assert "columns" in args

    def test_sort_descending_flag(self, parsed_steps):
        sort_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.sort"), None)
        assert sort_step is not None
        assert sort_step["args"].get("ascending") is False

    def test_summarize_has_group_by(self, parsed_steps):
        summ_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Transform.summarize"), None)
        assert summ_step is not None
        assert "group_by" in summ_step.get("args", {})
        assert summ_step["args"]["group_by"] == "Region"

    def test_summarize_has_aggregations(self, parsed_steps):
        summ_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Transform.summarize"), None)
        aggs = summ_step["args"].get("aggregations", {})
        assert "Revenue" in aggs
        assert aggs["Revenue"] == "sum"

    def test_select_columns_parsed(self, parsed_steps):
        sel_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.select"), None)
        assert sel_step is not None
        cols = sel_step.get("args", {}).get("columns", [])
        assert "Revenue" in cols
        # InternalNote was de-selected — must not appear
        assert "InternalNote" not in cols

    def test_formula_column_parsed(self, parsed_steps):
        form_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.formula"), None)
        assert form_step is not None
        assert form_step["args"].get("column") == "ProfitMargin"

    def test_filter_t_anchor_produces_dot_zero_ref(self, parsed_steps):
        """The Select step that receives Filter's T anchor should ref filter_step.0"""
        filter_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.filter"), None)
        select_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.select"), None)
        assert filter_step is not None and select_step is not None
        df_ref = select_step.get("inputs", {}).get("df", "")
        assert df_ref.endswith(".0"), f"Expected Select's input to reference Filter's T anchor (.0), got: {df_ref!r}"

    def test_filter_f_anchor_produces_dot_one_ref(self, parsed_steps):
        """The Formula step that receives Filter's F anchor should ref filter_step.1"""
        filter_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.filter"), None)
        form_step = next((s for s in parsed_steps["steps"] if s.get("tool") == "Preparation.formula"), None)
        assert filter_step is not None and form_step is not None
        df_ref = form_step.get("inputs", {}).get("df", "")
        assert df_ref.endswith(".1"), f"Expected Formula's input to reference Filter's F anchor (.1), got: {df_ref!r}"

    def test_steps_in_topological_order(self, parsed_steps):
        """Input step must appear before Filter, Filter before Select, etc."""
        steps = parsed_steps["steps"]
        tools = [s["tool"] for s in steps]
        input_idx = tools.index("InOut.input_data")
        filter_idx = tools.index("Preparation.filter")
        select_idx = tools.index("Preparation.select")
        summ_idx = tools.index("Transform.summarize")
        output_idx = tools.index("InOut.output_data")
        assert input_idx < filter_idx < select_idx < summ_idx < output_idx


class TestYxmdConverterSave:
    def test_save_writes_file(self, tmp_path):
        out_path = tmp_path / "output.yaml"
        c = YxmdConverter(SAMPLE_YXMD)
        c.save(out_path)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_saved_file_is_valid_yaml(self, tmp_path):
        out_path = tmp_path / "output.yaml"
        c = YxmdConverter(SAMPLE_YXMD)
        c.save(out_path)
        content = out_path.read_text(encoding="utf-8")
        stripped = "\n".join(ln for ln in content.splitlines() if not ln.startswith("#"))
        parsed = yaml.safe_load(stripped)
        assert "steps" in parsed

    def test_save_creates_parent_dirs(self, tmp_path):
        out_path = tmp_path / "nested" / "dir" / "pipeline.yaml"
        c = YxmdConverter(SAMPLE_YXMD)
        c.save(out_path)
        assert out_path.exists()


class TestYxmdConverterUnmappedPlugin:
    """An unknown plugin should generate a placeholder step, not crash."""

    WORKFLOW_WITH_UNKNOWN = """\
<?xml version="1.0" encoding="utf-8"?>
<WorkflowDocument yxmdVer="2023.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="SomeVendor.UnknownTool.UnknownTool">
        <Position x="10" y="10"/>
      </GuiSettings>
      <Properties><Configuration/></Properties>
    </Node>
  </Nodes>
  <Connections/>
</WorkflowDocument>
"""

    def test_unknown_plugin_does_not_crash(self, tmp_path):
        f = tmp_path / "unknown.yxmd"
        f.write_text(self.WORKFLOW_WITH_UNKNOWN, encoding="utf-8")
        c = YxmdConverter(f)
        yaml_text = c.to_yaml()
        assert "TODO_" in yaml_text

    def test_unknown_plugin_appears_in_warnings(self, tmp_path):
        f = tmp_path / "unknown.yxmd"
        f.write_text(self.WORKFLOW_WITH_UNKNOWN, encoding="utf-8")
        c = YxmdConverter(f)
        c.to_yaml()
        assert len(c.warnings) > 0

    def test_coverage_below_one_for_unknown(self, tmp_path):
        f = tmp_path / "unknown.yxmd"
        f.write_text(self.WORKFLOW_WITH_UNKNOWN, encoding="utf-8")
        c = YxmdConverter(f)
        assert c.coverage < 1.0


class TestYxmdConverterEmptyWorkflow:
    EMPTY_WORKFLOW = """\
<?xml version="1.0" encoding="utf-8"?>
<WorkflowDocument yxmdVer="2023.1">
  <Nodes/>
  <Connections/>
</WorkflowDocument>
"""

    def test_empty_workflow_produces_valid_yaml(self, tmp_path):
        f = tmp_path / "empty.yxmd"
        f.write_text(self.EMPTY_WORKFLOW, encoding="utf-8")
        c = YxmdConverter(f)
        yaml_text = c.to_yaml()
        assert "name:" in yaml_text
        assert "steps:" in yaml_text

    def test_empty_workflow_coverage_is_one(self, tmp_path):
        f = tmp_path / "empty.yxmd"
        f.write_text(self.EMPTY_WORKFLOW, encoding="utf-8")
        c = YxmdConverter(f)
        assert c.coverage == 1.0


class TestPublicApiExport:
    def test_yxmd_converter_importable_from_root(self):
        from etlpipe import YxmdConverter as YC

        assert YC is not None

    def test_yxmd_converter_is_same_class(self):
        from etlpipe import YxmdConverter as YC
        from etlpipe.convert import YxmdConverter

        assert YC is YxmdConverter
