"""differ 模块测试——验收用例 1,2,3,6
只比通用区；结构异常上报。missing_file 由 scanner 层处理。
"""
import pytest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> list[str]:
    path = FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return f.readlines()


from app.splitter import split_file, SplitResult, SplitStatus
from app.differ import diff_general, DiffResult, DiffState
from app.constants import DiffState


def _split(lines, cfg=None):
    if cfg is None:
        cfg = {"general_scope": "whole_file", "boundary_anchor": None}
    return split_file(lines, cfg)


class TestDifferClaude:
    """用例1: CLAUDE 整份同步 & 用例6: 已最新→不动"""

    def test_claude_outdated(self):
        hub_lines = _read_fixture("claude_hub.txt")
        spoke_lines = _read_fixture("claude_spoke_old.txt")
        hub = _split(hub_lines)
        spoke = _split(spoke_lines)
        result = diff_general(hub, spoke)
        assert result.state == DiffState.OUTDATED
        assert result.diff_text

    def test_claude_up_to_date(self):
        hub_lines = _read_fixture("claude_hub.txt")
        spoke_lines = _read_fixture("claude_spoke_same.txt")
        hub = _split(hub_lines)
        spoke = _split(spoke_lines)
        result = diff_general(hub, spoke)
        assert result.state == DiffState.UP_TO_DATE
        assert not result.diff_text


class TestDifferAgents:
    """用例2: AGENTS 保专属(核心红线) + 用例3: 审查清单保第二部分"""

    def test_agents_outdated_private_preserved(self):
        hub_lines = _read_fixture("agents_hub.txt")
        spoke_lines = _read_fixture("agents_spoke.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub = split_file(hub_lines, cfg)
        spoke = split_file(spoke_lines, cfg)
        assert hub.status == SplitStatus.OK
        assert spoke.status == SplitStatus.OK

        result = diff_general(hub, spoke)
        assert result.state == DiffState.OUTDATED
        assert "产品规划" not in (result.diff_text or "")
        assert "母版同步器" not in (result.diff_text or "")

    def test_checklist_outdated_private_preserved(self):
        hub_lines = _read_fixture("checklist_hub.txt")
        spoke_lines = _read_fixture("checklist_spoke.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub = split_file(hub_lines, cfg)
        spoke = split_file(spoke_lines, cfg)
        result = diff_general(hub, spoke)
        assert result.state == DiffState.OUTDATED
        assert "L12" not in (result.diff_text or "")
        assert "有向图" not in (result.diff_text or "")

    def test_agents_up_to_date(self):
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        lines = _read_fixture("agents_spoke.txt")
        hub = split_file(lines, cfg)
        spoke = split_file(lines, cfg)
        result = diff_general(hub, spoke)
        assert result.state == DiffState.UP_TO_DATE


class TestDifferNoBlankLines:
    """diff 文本无多余空行。"""

    def test_outdated_diff_has_no_consecutive_blank_lines(self):
        hub_lines = _read_fixture("claude_hub.txt")
        spoke_lines = _read_fixture("claude_spoke_old.txt")
        hub = _split(hub_lines)
        spoke = _split(spoke_lines)
        result = diff_general(hub, spoke)
        assert result.state == DiffState.OUTDATED
        assert result.diff_text
        assert "\n\n\n" not in result.diff_text

    def test_agents_diff_no_blank_lines(self):
        hub_lines = _read_fixture("agents_hub.txt")
        spoke_lines = _read_fixture("agents_spoke.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub = split_file(hub_lines, cfg)
        spoke = split_file(spoke_lines, cfg)
        result = diff_general(hub, spoke)
        assert result.state == DiffState.OUTDATED
        assert result.diff_text
        assert "\n\n\n" not in result.diff_text


class TestDifferErrorHandling:
    """结构异常路径。"""

    def test_hub_structure_error_returns_structure_error(self):
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub_error = SplitResult(status=SplitStatus.STRUCTURE_ERROR, general=[], private=[])
        spoke_ok = split_file(_read_fixture("agents_spoke.txt"), cfg)
        result = diff_general(hub_error, spoke_ok)
        assert result.state == DiffState.STRUCTURE_ERROR
        assert result.diff_text is None

    def test_spoke_structure_error_returns_structure_error(self):
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub_ok = split_file(_read_fixture("agents_hub.txt"), cfg)
        spoke_error = SplitResult(status=SplitStatus.STRUCTURE_ERROR, general=[], private=[])
        result = diff_general(hub_ok, spoke_error)
        assert result.state == DiffState.STRUCTURE_ERROR

    def test_both_structure_error(self):
        e = SplitResult(status=SplitStatus.STRUCTURE_ERROR, general=[], private=[])
        result = diff_general(e, e)
        assert result.state == DiffState.STRUCTURE_ERROR
