"""applier 红线测试——验收用例 2,3 完整版 + 用例 8,9

核心红线:
- 应用后专属区(# 第二部分及其后)逐字节不变
- 写入前已生成 .bak 备份
- dry-run 不产生任何写入
- 备份失败即止
"""
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> list[str]:
    path = FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return f.readlines()


from app.splitter import split_file, SplitStatus
from app.applier import apply_file
from app.constants import DiffState, MANAGED_FILE_MAP


class TestApplierRedLines:
    """applier 红线测试——必须通过。"""

    def _make_temp_spoke(self, tmpdir, src_fixture):
        """在临时目录创建 spoke 文件副本并返回路径。"""
        spoke_dir = tmpdir / "spoke"
        spoke_dir.mkdir()
        src = _read_fixture(src_fixture)
        spoke_path = spoke_dir / "AGENTS.md"
        spoke_path.write_text("".join(src), encoding="utf-8")
        return str(spoke_path)

    def test_agents_apply_preserves_private_exact(self, tmpdir):
        """用例2 完整版: hub AGENTS 第一部分有更新,spoke 有专属内容。
        应用后:
        ① 通用区已跟上 hub
        ② 专属区逐字节不变
        ③ 写入前有 .bak 备份
        """
        spoke_path = self._make_temp_spoke(tmpdir, "agents_spoke_full.txt")
        hub_general = _read_fixture("agents_hub.txt")

        # 切分 hub 和 spoke 得到通用区/专属区
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub_split = split_file(hub_general, cfg)
        spoke_orig = split_file(_read_fixture("agents_spoke_full.txt"), cfg)

        assert hub_split.status == SplitStatus.OK
        assert spoke_orig.status == SplitStatus.OK

        # 记录 spoke 原始专属区(字节级)
        spoke_private_original = "".join(spoke_orig.private)

        # 执行 apply (非 dry-run)
        result = apply_file(
            hub_dir=str(tmpdir),
            spoke_path=spoke_path,
            file_name="AGENTS.md",
            hub_general=hub_split.general,
            spoke_private=spoke_orig.private,
            dry_run=False,
        )

        assert result.success, f"apply 失败: {result.error}"

        # ③ 断言: .bak 备份已生成
        assert result.backup_path is not None
        assert os.path.isfile(result.backup_path)
        assert ".bak." in result.backup_path

        # 读取写回后的文件
        with open(spoke_path, encoding="utf-8") as f:
            written_text = f.read()

        # ① 断言: 通用区已更新(hub 的新规则行出现)
        assert "新增规则：所有公共函数必须有类型注解" in written_text

        # ② 断言: 专属区逐字节不变
        assert spoke_private_original in written_text
        # 专属内容原样在
        assert "供应链拓扑必须用有向图表示" in written_text
        assert "产品规划" in written_text

    def test_checklist_apply_preserves_private_exact(self, tmpdir):
        """用例3 完整版: 审查清单——hub 第一部分新增审查项,spoke 有 L12。
        应用后:
        ① 第一部分更新
        ② 第二部分(含 L12)原样保留
        ③ 备份存在
        """
        spoke_dir = tmpdir / "spoke"
        spoke_dir.mkdir()
        src = _read_fixture("checklist_spoke.txt")
        spoke_path = str(spoke_dir / "审查清单.md")
        with open(spoke_path, "w", encoding="utf-8") as f:
            f.writelines(src)

        hub_lines = _read_fixture("checklist_hub.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub_split = split_file(hub_lines, cfg)
        spoke_split = split_file(src, cfg)

        spoke_private_original = "".join(spoke_split.private)

        result = apply_file(
            hub_dir=str(tmpdir),
            spoke_path=spoke_path,
            file_name="审查清单.md",
            hub_general=hub_split.general,
            spoke_private=spoke_split.private,
            dry_run=False,
        )

        assert result.success
        assert result.backup_path is not None
        assert os.path.isfile(result.backup_path)

        with open(spoke_path, encoding="utf-8") as f:
            written_text = f.read()

        # ① 通用区更新(新增审查项出现)
        assert "规格符合(新增)" in written_text
        assert "是否有静默丢数据的行为" in written_text

        # ② 专属区原样保留
        assert spoke_private_original in written_text
        assert "L12 · 项目追加教训" in written_text
        assert "供应链拓扑必须用有向图表示" in written_text

    def test_dry_run_produces_no_write(self, tmpdir):
        """用例8: dry-run 不产生任何文件写入。"""
        spoke_dir = tmpdir / "spoke"
        spoke_dir.mkdir()
        src = _read_fixture("agents_spoke_full.txt")
        spoke_path = str(spoke_dir / "AGENTS.md")
        with open(spoke_path, "w", encoding="utf-8") as f:
            f.writelines(src)

        # 记录写入前 mtime
        orig_mtime = os.path.getmtime(spoke_path)
        orig_content = open(spoke_path, encoding="utf-8").read()

        hub_lines = _read_fixture("agents_hub.txt")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
        hub_split = split_file(hub_lines, cfg)
        spoke_split = split_file(src, cfg)

        result = apply_file(
            hub_dir=str(tmpdir),
            spoke_path=spoke_path,
            file_name="AGENTS.md",
            hub_general=hub_split.general,
            spoke_private=spoke_split.private,
            dry_run=True,
        )

        assert result.success
        # 没有备份
        assert result.backup_path is None
        # 文件未被修改
        assert os.path.getmtime(spoke_path) == orig_mtime
        assert open(spoke_path, encoding="utf-8").read() == orig_content

        # 目录下无 .bak 文件
        bak_files = list(Path(spoke_dir).glob("*.bak.*"))
        assert len(bak_files) == 0

    def test_backup_failure_aborts_write(self, tmpdir):
        """用例9: 模拟备份写入失败 → 文件不被覆盖,报告显式记错。

        策略: 让 spoke 文件的父目录在 copy2 前变成只读(无写权限),
        这样备份写入会触发 OSError，确保原始文件不被修改。
        """
        spoke_dir = tmpdir / "spoke"
        spoke_dir.mkdir()
        src = _read_fixture("claude_spoke_old.txt")
        spoke_path = str(spoke_dir / "CLAUDE.md")
        with open(spoke_path, "w", encoding="utf-8") as f:
            f.writelines(src)

        orig_content = "".join(src)

        # 把目录权限改为只读,阻止 copy2 写入备份文件
        os.chmod(spoke_dir, 0o555)  # r-x, 无 w

        try:
            hub_lines = _read_fixture("claude_hub.txt")
            hub_split = split_file(
                hub_lines,
                {"general_scope": "whole_file", "boundary_anchor": None},
            )

            result = apply_file(
                hub_dir=str(tmpdir),
                spoke_path=spoke_path,
                file_name="CLAUDE.md",
                hub_general=hub_split.general,
                spoke_private=[],
                dry_run=False,
            )

            # 应该失败
            assert not result.success
            assert "备份失败" in result.error
            assert result.backup_path is None

            # 恢复权限后检查原始文件未被修改
            os.chmod(spoke_dir, 0o755)
            with open(spoke_path, encoding="utf-8") as f:
                actual = f.read()
            assert actual == orig_content
        finally:
            os.chmod(spoke_dir, 0o755)

    def test_claude_whole_file_apply(self, tmpdir):
        """CLAUDE.md(whole_file): 直接用 hub 整份替换。"""
        spoke_dir = tmpdir / "spoke"
        spoke_dir.mkdir()
        src = _read_fixture("claude_spoke_old.txt")
        spoke_path = str(spoke_dir / "CLAUDE.md")
        with open(spoke_path, "w", encoding="utf-8") as f:
            f.writelines(src)

        hub_lines = _read_fixture("claude_hub.txt")
        hub_split = split_file(hub_lines, {"general_scope": "whole_file", "boundary_anchor": None})

        result = apply_file(
            hub_dir=str(tmpdir),
            spoke_path=spoke_path,
            file_name="CLAUDE.md",
            hub_general=hub_split.general,
            spoke_private=[],
            dry_run=False,
        )

        assert result.success
        assert result.backup_path is not None

        with open(spoke_path, encoding="utf-8") as f:
            written = f.read()

        # spoke 现在等于 hub 整份
        assert written == "".join(hub_lines)
        assert "复盘沉淀" in written
        assert "CodeX 指令自包含" in written
