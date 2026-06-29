"""lesson_applier 测试——验收用例 16-24"""
import os
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> list[str]:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return f.readlines()


from app.lesson_parser import parse_lessons, Lesson
from app.lesson_applier import write_hub, write_spoke, ApplyResult


def _write_file(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _make_hub_file(tmpdir, private_lines):
    """创建带锚点的完整审查清单.md。"""
    # 如果 private_lines 首行已是锚点，去掉以避免双锚点
    if private_lines and private_lines[0].startswith("# 第二部分"):
        private_lines = private_lines[1:]
    path = str(tmpdir / "审查清单.md")
    lines = [
        "# 审查清单\n",
        "\n",
        "# 第一部分\n",
        "## 1. 契约一致性\n",
        "- 字段映射是否照搬。\n",
        "\n",
        "# 第二部分\n",
        "\n",
    ] + private_lines
    _write_file(path, lines)
    return path


class TestWriteHub:
    """用例 16-20"""

    def test_insert_new_lesson(self, tmpdir):
        """用例16: insert L14——hub 最大 L13，插入后 L13 之后 L14，第一部分不变。"""
        private = _read_fixture("lesson_private_normal.txt")
        path = _make_hub_file(tmpdir, private)
        orig_mtime = os.path.getmtime(path)

        new_lesson = Lesson(
            l_number=14,
            raw_lines=["- **L14 · 新教训(项目A)**:新教训内容。\n"],
            has_up_marker=False,
        )

        result = write_hub(path, new_lesson, "insert", dry_run=False)
        assert result.success
        assert result.backup_path is not None
        assert os.path.isfile(result.backup_path)

        with open(path, encoding="utf-8") as f:
            content = f.read()

        assert "L14" in content
        assert "新教训" in content
        assert "第一部分" in content
        assert "契约一致性" in content

    def test_insert_middle_l_number(self, tmpdir):
        """用例17: hub 有 L13、L15，插入 L14 → 顺序 L13/L14/L15。"""
        private = [
            "# 第二部分\n",
            "\n",
            "- **L13 · 13 号教训**:十三。\n",
            "- **L15 · 15 号教训**:十五。\n",
        ]
        path = _make_hub_file(tmpdir, private)

        new_lesson = Lesson(
            l_number=14,
            raw_lines=["- **L14 · 14 号教训**:十四。\n"],
            has_up_marker=False,
        )

        result = write_hub(path, new_lesson, "insert", dry_run=False)
        assert result.success

        lessons = parse_lessons(open(path, encoding="utf-8").readlines())
        nums = [l.l_number for l in lessons]
        assert nums == [13, 14, 15]

    def test_replace_update(self, tmpdir):
        """用例18: replace L8——内容更新，其余不变。"""
        private = _read_fixture("lesson_hub_basic.txt")
        path = _make_hub_file(tmpdir, private)

        new_lesson = Lesson(
            l_number=8,
            raw_lines=["- **L8 · 更新后的 L8**:全新内容。\n"],
            has_up_marker=False,
        )

        result = write_hub(path, new_lesson, "replace", dry_run=False)
        assert result.success

        content = open(path, encoding="utf-8").read()
        assert "全新内容" in content
        assert "L1 · 符号方向" in content
        assert "旧版 L8 原文" not in content

    def test_dry_run_no_write(self, tmpdir):
        """用例19: dry-run 不写文件，无备份。"""
        private = _read_fixture("lesson_private_normal.txt")
        path = _make_hub_file(tmpdir, private)
        orig_mtime = os.path.getmtime(path)

        new_lesson = Lesson(l_number=14, raw_lines=["- **L14**:test\n"], has_up_marker=False)
        result = write_hub(path, new_lesson, "insert", dry_run=True)
        assert result.success
        assert result.backup_path is None
        assert os.path.getmtime(path) == orig_mtime

    def test_backup_failure_aborts(self, tmpdir):
        """用例20: 备份失败 → 不写文件。"""
        private = _read_fixture("lesson_private_normal.txt")
        path = _make_hub_file(tmpdir, private)
        orig = open(path, encoding="utf-8").read()

        # 将目录设只读以触发备份失败
        dir_path = os.path.dirname(path)
        os.chmod(dir_path, 0o555)

        try:
            new_lesson = Lesson(l_number=14, raw_lines=["- **L14**:test\n"], has_up_marker=False)
            result = write_hub(path, new_lesson, "insert", dry_run=False)
            assert not result.success
            assert "备份失败" in result.error
            assert open(path, encoding="utf-8").read() == orig
        finally:
            os.chmod(dir_path, 0o755)


class TestWriteSpoke:
    """用例 21-24"""

    def _make_spoke(self, tmpdir, private_lines):
        path = str(tmpdir / "审查清单.md")
        lines = ["# 审查清单\n", "\n", "# 第一部分\n", "content\n", "\n"] + private_lines
        _write_file(path, lines)
        return path

    def test_normal_down_insert(self, tmpdir):
        """用例21: spoke 有 L1-L13，插入 L14 → L14 在 L13 之后。"""
        private = _read_fixture("lesson_private_normal.txt")
        path = self._make_spoke(tmpdir, private)

        new_lesson = Lesson(
            l_number=14,
            raw_lines=["- **L14 · 新教训**:内容。\n"],
            has_up_marker=False,
        )

        result = write_spoke(path, new_lesson, dry_run=False)
        assert result.success
        assert result.backup_path

        content = open(path, encoding="utf-8").read()
        assert "L14" in content
        assert "第一部分" in content

    def test_insert_conflict(self, tmpdir):
        """用例22: spoke 已有 L14 → 返回 error，不写。"""
        private = _read_fixture("lesson_private_up_marker.txt")
        path = self._make_spoke(tmpdir, private)
        orig = open(path, encoding="utf-8").read()

        new_lesson = Lesson(
            l_number=14,
            raw_lines=["- **L14 · 冲突**:该号已存在。\n"],
            has_up_marker=False,
        )

        result = write_spoke(path, new_lesson, dry_run=False)
        assert not result.success
        assert "insert_conflict" in result.error
        assert open(path, encoding="utf-8").read() == orig

    def test_dry_run_no_write(self, tmpdir):
        """用例23: dry-run 不写文件。"""
        private = _read_fixture("lesson_private_normal.txt")
        path = self._make_spoke(tmpdir, private)
        orig_mtime = os.path.getmtime(path)

        new_lesson = Lesson(l_number=14, raw_lines=["- **L14**:test\n"], has_up_marker=False)
        result = write_spoke(path, new_lesson, dry_run=True)
        assert result.success
        assert result.backup_path is None
        assert os.path.getmtime(path) == orig_mtime

    def test_spoke_only_preserved(self, tmpdir):
        """用例24: spoke 有 L100(专属)，insert 后完整保留。"""
        private = [
            "# 第二部分\n",
            "- **L1 · 一号**:内容。\n",
            "- **L100 · Spoke 专属**:只在此处。\n",
        ]
        path = self._make_spoke(tmpdir, private)

        new_lesson = Lesson(
            l_number=50,
            raw_lines=["- **L50 · 中间插入**:插在中间。\n"],
            has_up_marker=False,
        )

        result = write_spoke(path, new_lesson, dry_run=False)
        assert result.success

        lessons = parse_lessons(open(path, encoding="utf-8").readlines())
        nums = [l.l_number for l in lessons]
        assert nums == [1, 50, 100]
        assert "Spoke 专属" in open(path, encoding="utf-8").read()
