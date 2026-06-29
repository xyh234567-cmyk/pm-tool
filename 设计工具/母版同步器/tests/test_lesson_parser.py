"""lesson_parser 测试——验收用例 1-5"""
import pytest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> list[str]:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return f.readlines()


from app.lesson_parser import parse_lessons, Lesson


class TestLessonParser:
    def test_parse_normal_lessons(self):
        """用例1: 正常多条教训 L1/L2/L3 → 3 个 Lesson。"""
        lines = _read_fixture("lesson_private_normal.txt")
        lessons = parse_lessons(lines)
        assert len(lessons) == 3
        assert lessons[0].l_number == 1
        assert lessons[1].l_number == 2
        assert lessons[2].l_number == 3
        assert "符号方向" in lessons[0].raw_lines[0]
        assert "schema 留关联" in lessons[1].raw_lines[0]
        assert "测试舒适区盲点" in lessons[2].raw_lines[0]

    def test_parse_multiline_lesson(self):
        """用例2: 含续行——L5 跨 3 行，raw_lines 含全部。"""
        lines = _read_fixture("lesson_private_multiline.txt")
        lessons = parse_lessons(lines)
        assert len(lessons) == 2
        l5 = [l for l in lessons if l.l_number == 5][0]
        assert len(l5.raw_lines) == 3
        assert "合成数据掩盖" in l5.raw_lines[0]
        assert "**铁律**" in l5.raw_lines[1]

    def test_up_marker_detection(self):
        """用例3: 含 [↑] 的条目 has_up_marker=True，不含的=False。"""
        lines = _read_fixture("lesson_private_up_marker.txt")
        lessons = parse_lessons(lines)
        l14 = [l for l in lessons if l.l_number == 14][0]
        l15 = [l for l in lessons if l.l_number == 15][0]
        l16 = [l for l in lessons if l.l_number == 16][0]
        assert l14.has_up_marker is True
        assert l15.has_up_marker is True
        assert l16.has_up_marker is False

    def test_empty_private(self):
        """用例4: 空第二部分(只有锚点行)→ 返回空列表。"""
        lines = _read_fixture("lesson_private_empty.txt")
        lessons = parse_lessons(lines)
        assert lessons == []

    def test_no_lesson_format(self):
        """用例5: 第二部分只有散文无 L 格式 → 返回空列表。"""
        lines = _read_fixture("lesson_private_no_lessons.txt")
        lessons = parse_lessons(lines)
        assert lessons == []

    def test_up_marker_not_in_continuation(self):
        """延续行中的 [↑] 不应触发 has_up_marker。"""
        lines = [
            "# 第二部分\n",
            "- **L1 · 标题(来源)**:内容。\n",
            "  续行含 [↑] 但不是起始行。\n",
        ]
        lessons = parse_lessons(lines)
        assert lessons[0].has_up_marker is False
