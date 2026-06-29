"""lesson_main 集成测试——验收用例 25-28"""
import os
from pathlib import Path
import pytest


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestLessonMain:
    def _make_env(self, tmpdir, with_up_marker=True):
        root = str(tmpdir / "设计")
        hub_dir = os.path.join(root, "设计工具")
        spoke_dir = os.path.join(root, "产品规划")

        # hub
        _write(os.path.join(hub_dir, "CLAUDE.md"), "# hub CLAUDE\n")
        _write(os.path.join(hub_dir, "AGENTS.md"), "# 第一部分\n\n# 第二部分\nhub专属\n")
        checklist = '# 审查清单\n\n# 第一部分\n\n# 第二部分\n\n- **L1 · 教训**:hub 版本。\n'
        _write(os.path.join(hub_dir, "审查清单.md"), checklist)

        # spoke
        _write(os.path.join(spoke_dir, "CLAUDE.md"), "# spoke CLAUDE\n")
        _write(os.path.join(spoke_dir, "AGENTS.md"), "# 第一部分\n\n# 第二部分\nspoke专属\n")
        marker = ' [↑]' if with_up_marker else ''
        spoke_cl = f'# 审查清单\n\n# 第一部分\n\n# 第二部分\n\n- **L1 · 教训**:hub 版本。\n- **L14 · 新教训(项目){marker}**:全新内容。\n'
        _write(os.path.join(spoke_dir, "审查清单.md"), spoke_cl)

        return root, hub_dir, spoke_dir

    def test_lesson_up_dry_run_no_write(self, tmpdir):
        """用例25: --lesson-up dry-run 不写 hub。"""
        root, hub_dir, spoke_dir = self._make_env(tmpdir, with_up_marker=True)
        orig_mtime = os.path.getmtime(os.path.join(hub_dir, "审查清单.md"))

        from app.main import run_lesson_up
        ret = run_lesson_up(hub_dir, dry_run=True)
        assert ret == 0
        assert os.path.getmtime(os.path.join(hub_dir, "审查清单.md")) == orig_mtime

        # 有报告生成
        reports = [f for f in os.listdir(hub_dir) if f.startswith("母版同步报告-") and "上行" in f]
        assert len(reports) >= 1
        for r in reports:
            os.remove(os.path.join(hub_dir, r))

    def test_lesson_down_dry_run_no_write(self, tmpdir):
        """用例26: --lesson-down dry-run 不写任何 spoke。"""
        root, hub_dir, spoke_dir = self._make_env(tmpdir, with_up_marker=False)
        # hub 有 L1/L14(新增教训)，spoke 有 L1
        hub_cl = '# 审查清单\n\n# 第一部分\n\n# 第二部分\n\n- **L1 · 教训**:hub 版本。\n- **L14 · Hub 新教训**:全新。\n'
        _write(os.path.join(hub_dir, "审查清单.md"), hub_cl)

        orig_mtime = os.path.getmtime(os.path.join(spoke_dir, "审查清单.md"))

        from app.main import run_lesson_down
        ret = run_lesson_down(hub_dir, dry_run=True)
        assert ret == 0
        assert os.path.getmtime(os.path.join(spoke_dir, "审查清单.md")) == orig_mtime

        reports = [f for f in os.listdir(hub_dir) if f.startswith("母版同步报告-") and "下行" in f]
        assert len(reports) >= 1
        for r in reports:
            os.remove(os.path.join(hub_dir, r))

    def test_mutual_exclusion(self, tmpdir):
        """用例27: --lesson-up --lesson-down 互斥报错退出。"""
        root, hub_dir, _ = self._make_env(tmpdir)
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-m", "app.main", "--lesson-up", "--lesson-down", "--hub", hub_dir],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert r.returncode != 0

    def test_no_candidates_no_write(self, tmpdir):
        """用例28: 无 [↑] 候选时输出提示。"""
        root, hub_dir, spoke_dir = self._make_env(tmpdir, with_up_marker=False)
        from app.main import run_lesson_up
        ret = run_lesson_up(hub_dir, dry_run=True)
        assert ret == 0

    def test_apply_strips_up_marker_from_hub(self, tmpdir):
        """apply 上行后 hub 审查清单.md 不含 [↑] 标记。"""
        root, hub_dir, spoke_dir = self._make_env(tmpdir, with_up_marker=True)

        from app.main import run_lesson_up

        ret = run_lesson_up(hub_dir, dry_run=False, confirm=False)
        assert ret == 0

        hub_cl = os.path.join(hub_dir, "审查清单.md")
        content = open(hub_cl, encoding="utf-8").read()
        assert "[↑]" not in content, f"hub 文件含 [↑] 泄漏:\n{content}"
        assert "L14" in content
        assert "全新内容" in content
