"""入口冒烟测试 — 确保 import 不抛错 + dry-run/apply 流水线可执行。"""
import os


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestMainImport:
    """纯导入即可抓语法/导入错误。"""

    def test_import_main(self):
        import app.main  # noqa: F401


class TestMainDryRun:
    """dry-run 冒烟: 造 hub+spoke, 跑流水线, 断言无副作用。"""

    def _make_design_root(self, tmpdir):
        root = str(tmpdir / "设计")
        _write(os.path.join(root, "设计工具", "CLAUDE.md"), "# hub CLAUDE\n## rules\n")
        _write(os.path.join(root, "设计工具", "AGENTS.md"), "# 第一部分\n\n# 第二部分\nhub专属\n")
        _write(os.path.join(root, "设计工具", "审查清单.md"), "# 第一部分\n\n# 第二部分\nhub教训\n")
        _write(os.path.join(root, "产品规划", "CLAUDE.md"), "# hub CLAUDE\n")
        _write(os.path.join(root, "产品规划", "AGENTS.md"), "# 第一部分\n\n# 第二部分\n产品专属\n")
        _write(os.path.join(root, "产品规划", "审查清单.md"), "# 第一部分\n\n# 第二部分\n产品教训L12\n")
        return root

    def test_dry_run_no_write(self, tmpdir):
        root = self._make_design_root(tmpdir)
        hub_dir = os.path.join(root, "设计工具")

        spoke_files = {}
        for fname in ["CLAUDE.md", "AGENTS.md", "审查清单.md"]:
            fp = os.path.join(root, "产品规划", fname)
            spoke_files[fname] = (os.path.getmtime(fp), open(fp, encoding="utf-8").read())

        from app.main import run
        ret = run(hub_dir, dry_run=True)
        assert ret == 0

        for fname, (orig_mtime, orig_content) in spoke_files.items():
            fp = os.path.join(root, "产品规划", fname)
            assert os.path.getmtime(fp) == orig_mtime, f"{fname} 的 mtime 变了"
            assert open(fp, encoding="utf-8").read() == orig_content, f"{fname} 的内容变了"

        reports = [f for f in os.listdir(hub_dir) if f.startswith("母版同步报告-") and f.endswith(".md")]
        assert len(reports) >= 1, "dry-run 应该生成 Markdown 报告"

        for r in reports:
            os.remove(os.path.join(hub_dir, r))

    def test_apply_no_error(self, tmpdir):
        """apply 模式 + 有 outdated 项 → 不抛 NameError，文件被正确写入。"""
        root = str(tmpdir / "设计")
        hub_dir = os.path.join(root, "设计工具")
        spoke_dir = os.path.join(root, "产品规划")

        _write(os.path.join(hub_dir, "CLAUDE.md"), "# 通用\n新内容\n")
        _write(os.path.join(spoke_dir, "CLAUDE.md"), "# 通用\n旧内容\n")
        for fname in ["AGENTS.md", "审查清单.md"]:
            content = "# 第一部分\ncontent\n# 第二部分\n专属\n"
            _write(os.path.join(hub_dir, fname), content)
            _write(os.path.join(spoke_dir, fname), content)

        from app.main import run
        ret = run(hub_dir, dry_run=False, confirm=False)
        assert ret == 0

        written = open(os.path.join(spoke_dir, "CLAUDE.md"), encoding="utf-8").read()
        assert "新内容" in written

        baks = [f for f in os.listdir(spoke_dir) if f.startswith("CLAUDE.md.bak.")]
        assert len(baks) == 1, "apply 后应有一个备份文件"

        for f in os.listdir(hub_dir):
            if f.startswith("母版同步报告-"):
                os.remove(os.path.join(hub_dir, f))
