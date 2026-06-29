"""bootstrap 测试——验收用例 1-4 + 回归"""
import os
import pytest
from app.bootstrap import create_project

def _make_root(tmpdir):
    from pathlib import Path
    root = str(tmpdir / "设计")
    hub = os.path.join(root, "设计工具")
    os.makedirs(hub, exist_ok=True)
    for fn, txt in [("CLAUDE.md", "# hub CLAUDE\n"),
                    ("AGENTS.md", "# 第一部分\n\n# 第二部分\n专属\n"),
                    ("审查清单.md", "# 审查清单\n\n# 第一部分\n\n# 第二部分\n")]:
        with open(os.path.join(hub, fn), "w", encoding="utf-8") as f:
            f.write(txt)
    return root

class TestCreateProject:
    def test_create_normal(self, tmpdir):
        root = _make_root(tmpdir)
        result = create_project(root, "产品规划")
        assert result.success
        assert len(result.created_files) == 6

    def test_duplicate_name_rejected(self, tmpdir):
        root = _make_root(tmpdir)
        create_project(root, "产品规划")
        result = create_project(root, "产品规划")
        assert not result.success
        assert "已存在" in result.error

    def test_missing_hub_template_aborts(self, tmpdir):
        root = _make_root(tmpdir)
        os.remove(os.path.join(root, "设计工具", "AGENTS.md"))
        result = create_project(root, "新项目")
        assert not result.success
        assert "AGENTS.md" in result.error

    def test_skeleton_content_matches(self, tmpdir):
        root = _make_root(tmpdir)
        result = create_project(root, "产品规划")
        assert result.success
        dr = open(os.path.join(root, "产品规划", "决策记录.md"), encoding="utf-8").read()
        assert "append-only" in dr

    def test_empty_name_rejected(self, tmpdir):
        root = _make_root(tmpdir)
        assert not create_project(root, "").success
    def test_creates_in_root_directory(self, tmpdir):
        root = _make_root(tmpdir)
        result = create_project(root, "测试项目")
        assert result.success
        assert not os.path.exists(os.path.join(root, "设计工具", "测试项目"))
