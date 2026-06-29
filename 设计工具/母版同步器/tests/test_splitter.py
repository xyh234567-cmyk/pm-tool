"""splitter 模块测试——验收用例 1,2,3,4,5
先写测试，再实现。覆盖正例和负例(缺锚点、多锚点)。
"""
import pytest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> list[str]:
    """读取测试样例文件，返回行列表(保留换行符)。"""
    path = FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return f.readlines()


# ---- splitter 导入(测试先行——实现后此 import 才有效) ----
from app.splitter import split_file, SplitResult, SplitStatus


class TestSplitterWholeFile:
    """CLAUDE.md: general_scope=whole_file，整份都是通用区。"""

    def test_claude_whole_file_returns_all_general(self):
        """用例1 前置: whole_file 类型的切分，通用区 = 全文。"""
        lines = _read_fixture("claude_hub.txt")
        cfg = {"general_scope": "whole_file", "boundary_anchor": None}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.OK
        assert result.general == lines
        assert result.private == []


class TestSplitterBeforeAnchor:
    """AGENTS.md / 审查清单.md: general_scope=before_anchor。"""

    def test_agents_with_anchor_returns_two_sections(self):
        """正常: 恰好一个 # 第二部分 锚点,切出通用区+专属区。"""
        lines = _read_fixture("agents_spoke.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.OK
        assert len(result.general) > 0
        assert len(result.private) > 0
        # 专属区第一行必须是锚点行
        assert result.private[0].startswith("# 第二部分")
        # 通用区不应包含锚点
        assert not any(line.startswith("# 第二部分") for line in result.general)

    def test_checklist_with_anchor_returns_two_sections(self):
        """审查清单同理。"""
        lines = _read_fixture("checklist_hub.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.OK
        assert len(result.general) > 0
        assert len(result.private) > 0
        assert result.private[0].startswith("# 第二部分")

    def test_no_anchor_returns_structure_error(self):
        """用例4: 缺锚点 → structure_error。"""
        lines = _read_fixture("agents_no_anchor.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.STRUCTURE_ERROR
        assert result.general == []
        assert result.private == []

    def test_double_anchor_returns_structure_error(self):
        """用例5: 多锚点 → structure_error。"""
        lines = _read_fixture("agents_double_anchor.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.STRUCTURE_ERROR
        assert result.general == []
        assert result.private == []

    def test_checklist_no_anchor_returns_structure_error(self):
        """审查清单缺锚点同理。"""
        lines = _read_fixture("checklist_no_anchor.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.STRUCTURE_ERROR

    def test_anchor_with_leading_whitespace_not_matched(self):
        """锚点匹配规则: strip_leading_whitespace=false → 行首有空白不算锚点。
        即 顶格的 "# 第二部分" 才是锚点。缩进的不算。"""
        text = """# AGENTS.md

# 第一部分

   # 第二部分  <-- 这个前有空白,不算锚点

# 第二部分 · 项目专属

## 专属内容
"""
        lines = text.splitlines(keepends=True)
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        # 有两个顶格的 "# 第二部分"? 文本里第一个 "# 第一部分" 不是锚点。
        # 第二个 "# 第二部分" 缩进的也不算。
        # 第三个 "# 第二部分 · 项目专属" 是唯一顶格锚点。
        assert result.status == SplitStatus.OK
        assert len(result.general) > 0
        assert len(result.private) > 0

    def test_anchor_with_suffix_still_matches(self):
        """锚点行允许带后缀(如 "# 第二部分 · 项目专属")——匹配前缀。"""
        text = """# AGENTS.md

# 第一部分

# 第二部分 · 项目专属(产品规划)

## 专属内容
"""
        lines = text.splitlines(keepends=True)
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.OK
        assert result.private[0].startswith("# 第二部分")


class TestSplitterEdgeCases:
    """边界情况。"""

    def test_empty_file(self):
        """空文件 → structure_error(找不到锚点)。"""
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file([], cfg)
        assert result.status == SplitStatus.STRUCTURE_ERROR

    def test_anchor_is_first_line(self):
        """锚点在第一行 → 通用区为空。"""
        text = """# 第二部分 · 项目专属

专属。
"""
        lines = text.splitlines(keepends=True)
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.OK
        assert result.general == []
        assert len(result.private) > 0

    def test_anchor_is_last_line(self):
        """锚点在最后一行 → 专属区只有锚点行。"""
        text = """通用内容。

# 第二部分
"""
        lines = text.splitlines(keepends=True)
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        result = split_file(lines, cfg)
        assert result.status == SplitStatus.OK
        assert len(result.general) > 0
        assert result.private == ["# 第二部分\n"]

    def test_whole_file_empty(self):
        """whole_file 空文件 → 通用区空。"""
        cfg = {"general_scope": "whole_file", "boundary_anchor": None}
        result = split_file([], cfg)
        assert result.status == SplitStatus.OK
        assert result.general == []
        assert result.private == []
