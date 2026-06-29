"""scanner 测试——验收用例 7,7b,10: 缺件提醒 + 无关目录静默跳过"""
import os
import shutil
import pytest

from app.scanner import scan, SpokeFilePair
from app.constants import DiffState


def _write(path, text):
    with open(str(path), "w", encoding="utf-8") as f:
        f.write(text)


class TestScanner:
    """模拟目录结构测试扫描逻辑。"""

    def _make_fake_root(self, tmpdir):
        root = str(tmpdir / "设计")
        os.makedirs(root, exist_ok=True)

        hub = os.path.join(root, "设计工具")
        os.makedirs(hub, exist_ok=True)
        for f in ["CLAUDE.md", "AGENTS.md", "审查清单.md"]:
            _write(os.path.join(hub, f), f"hub {f}")

        spoke = os.path.join(root, "产品规划")
        os.makedirs(spoke, exist_ok=True)
        for f in ["CLAUDE.md", "AGENTS.md", "审查清单.md"]:
            _write(os.path.join(spoke, f), f"spoke {f}")

        old = os.path.join(root, "旧项目")
        os.makedirs(old, exist_ok=True)
        _write(os.path.join(old, "CLAUDE.md"), "old")

        os.makedirs(os.path.join(root, "历史归档"), exist_ok=True)
        os.makedirs(os.path.join(root, ".hidden"), exist_ok=True)

        return root, hub

    def test_scan_finds_valid_spoke(self, tmpdir):
        root, hub = self._make_fake_root(tmpdir)
        pairs = scan(hub)

        spoke_names = {p.spoke_name for p in pairs}
        assert "产品规划" in spoke_names
        assert "旧项目" not in spoke_names
        assert "历史归档" not in spoke_names
        assert "设计工具" not in spoke_names

        assert len(pairs) == 3
        for p in pairs:
            assert p.spoke_name == "产品规划"
            assert p.file_name in ("CLAUDE.md", "AGENTS.md", "审查清单.md")

    def test_old_project_not_scanned(self, tmpdir):
        """用例10: 无三件套且无 marker → 静默跳过。"""
        root, hub = self._make_fake_root(tmpdir)
        pairs = scan(hub)
        assert len([p for p in pairs if p.spoke_name == "旧项目"]) == 0

    def test_excluded_dirs_not_scanned(self, tmpdir):
        root, hub = self._make_fake_root(tmpdir)
        pairs = scan(hub)
        assert len([p for p in pairs if p.spoke_name == "历史归档"]) == 0
        assert len([p for p in pairs if p.spoke_name == "设计工具"]) == 0

    def test_hidden_dirs_not_scanned(self, tmpdir):
        root, hub = self._make_fake_root(tmpdir)
        pairs = scan(hub)
        assert len([p for p in pairs if p.spoke_name.startswith(".")]) == 0

    def test_incomplete_with_marker_reports_missing(self, tmpdir):
        """用例7: 含 marker 但三件套不全 → missing_file, present 不同步。"""
        root, hub = self._make_fake_root(tmpdir)

        partial = os.path.join(root, "产品规划")
        os.remove(os.path.join(partial, "AGENTS.md"))

        pairs = scan(hub)

        missing = [p for p in pairs if p.state == DiffState.MISSING_FILE]
        assert len(missing) == 1
        assert missing[0].file_name == "AGENTS.md"
        assert missing[0].spoke_name == "产品规划"
        assert "AGENTS.md" in missing[0].error_reason

        present_files = {p.file_name for p in pairs}
        assert "CLAUDE.md" not in present_files
        assert "审查清单.md" not in present_files

    def test_incomplete_no_marker_silently_skipped(self, tmpdir):
        """用例7b: 无 marker 且三件套不全 → 静默跳过。"""
        root, hub = self._make_fake_root(tmpdir)

        only_claude = os.path.join(root, "old_claude_only")
        os.makedirs(only_claude, exist_ok=True)
        _write(os.path.join(only_claude, "CLAUDE.md"), "only claude")

        pairs = scan(hub)
        names = {p.spoke_name for p in pairs}
        assert "old_claude_only" not in names


    def test_incomplete_missing_checklist_but_has_agents(self, tmpdir):
        """用例7c: 缺审查清单.md、有 AGENTS.md(marker) → 仍报 missing_file。"""
        root, hub = self._make_fake_root(tmpdir)

        partial = os.path.join(root, "产品规划")
        os.remove(os.path.join(partial, "审查清单.md"))
        # 此时: CLAUDE.md(present), AGENTS.md(present=marker)

        pairs = scan(hub)

        missing = [p for p in pairs if p.state == DiffState.MISSING_FILE]
        assert len(missing) == 1
        assert missing[0].file_name == "审查清单.md"
        assert missing[0].spoke_name == "产品规划"
        assert "审查清单.md" in missing[0].error_reason

        # present 文件不同步
        present_files = {p.file_name for p in pairs}
        assert "CLAUDE.md" not in present_files
        assert "AGENTS.md" not in present_files

    def test_no_spokes_returns_empty(self, tmpdir):
        root, hub = self._make_fake_root(tmpdir)
        shutil.rmtree(os.path.join(root, "产品规划"))
        pairs = scan(hub)
        assert pairs == []

    def test_hub_not_exists_raises(self, tmpdir):
        with pytest.raises(FileNotFoundError):
            scan(os.path.join(str(tmpdir), "nonexistent"))
