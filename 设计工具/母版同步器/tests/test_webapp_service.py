"""webapp service 层测试——验收用例 1-6"""
import os
import pytest


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _make_hub_spoke(tmpdir, spoke_extra=None, missing_files=None, structure_error_files=None):
    """造一套 hub + spoke 的合成目录。

    hub 有标准 CLAUDE/AGENTS/审查清单。
    spoke 默认与 hub 完全一致（up_to_date）。
    spoke_extra: dict[fname->text] 覆盖 spoke 文件内容（制造 outdated）。
    missing_files: set[str] 从 spoke 删掉的文件名。
    structure_error_files: set[str] 在 spoke 中删掉锚点行的文件名。
    """
    root = str(tmpdir / "设计")
    hub_dir = os.path.join(root, "设计工具")
    spoke_dir = os.path.join(root, "产品规划")

    hub_claude = "# hub CLAUDE\n通用区内容。\n"
    hub_agents = "# hub AGENTS\n\n# 第一部分\n通用规则。\n\n# 第二部分\nhub 专属。\n"
    hub_checklist = "# 审查清单\n\n# 第一部分\n通用审查项。\n\n# 第二部分\n\n- **L1 · 符号方向**:内容。\n- **L2 · schema 留关联**:内容。\n"

    _write(os.path.join(hub_dir, "CLAUDE.md"), hub_claude)
    _write(os.path.join(hub_dir, "AGENTS.md"), hub_agents)
    _write(os.path.join(hub_dir, "审查清单.md"), hub_checklist)

    spoke_extra = spoke_extra or {}
    missing_files = missing_files or set()
    structure_error_files = structure_error_files or set()

    for fname, hub_text in [("CLAUDE.md", hub_claude), ("AGENTS.md", hub_agents), ("审查清单.md", hub_checklist)]:
        if fname in missing_files:
            continue
        text = spoke_extra.get(fname, hub_text)
        if fname in structure_error_files:
            # 删掉 "# 第二部分" 锚点行，制造 structure_error
            text = text.replace("# 第二部分", "")
        _write(os.path.join(spoke_dir, fname), text)

    return hub_dir, spoke_dir


class TestScanGeneral:
    """用例 1-2: scan_general 状态分类"""

    def test_outdated_and_up_to_date(self, tmpdir):
        """用例1: outdated 项 diff 非空;最新项 diff 为空。"""
        hub_dir, spoke_dir = _make_hub_spoke(tmpdir, spoke_extra={
            "CLAUDE.md": "# spoke CLAUDE\n旧版本内容。\n",
        })

        from webapp.service import scan_general
        results = scan_general(hub_dir)

        # 找产品规划的项
        spoke_items = [r for r in results if r["spoke_name"] == "产品规划"]
        assert len(spoke_items) == 3  # CLAUDE + AGENTS + 审查清单

        claude = [r for r in spoke_items if r["file_name"] == "CLAUDE.md"][0]
        agents = [r for r in spoke_items if r["file_name"] == "AGENTS.md"][0]

        assert claude["state"] == "outdated"
        assert claude["can_apply"] is True
        assert claude["diff_text"]
        assert agents["state"] == "up_to_date"
        assert agents["can_apply"] is False

    def test_missing_file_and_structure_error(self, tmpdir):
        """用例2: 结构异常项正确标记且不可写。"""
        hub_dir, _ = _make_hub_spoke(
            tmpdir,
            structure_error_files={"AGENTS.md"},
        )

        from webapp.service import scan_general
        results = scan_general(hub_dir)
        spoke_items = [r for r in results if r["spoke_name"] == "产品规划"]


        structure = [r for r in spoke_items if r["file_name"] == "AGENTS.md"][0]
        assert structure["state"] == "structure_error"
        assert structure["can_apply"] is False


class TestApplyGeneral:
    """用例 3-4: apply_general 写入 + 拒绝非法项"""

    def test_apply_outdated_preserves_private_and_backup(self, tmpdir):
        """用例3: 写 outdated 项 → 通用区更新、专属区不变、生成 .bak。"""
        hub_dir, spoke_dir = _make_hub_spoke(tmpdir, spoke_extra={
            "AGENTS.md": "# hub AGENTS\n\n# 第一部分\n更新后的通用规则。\n\n# 第二部分\nspoke 专属区域内容。\n",
        })

        from webapp.service import scan_general, apply_general

        # 先扫描确认 outdated
        results = scan_general(hub_dir)
        agents = [r for r in results if r["file_name"] == "AGENTS.md" and r["spoke_name"] == "产品规划"][0]
        assert agents["state"] == "outdated"

        # 执行写入
        apply_result = apply_general(hub_dir, [{
            "spoke_name": "产品规划",
            "file_name": "AGENTS.md",
        }])

        assert len(apply_result) == 1
        assert apply_result[0]["success"] is True
        assert apply_result[0]["backup_path"]
        assert os.path.isfile(apply_result[0]["backup_path"])

        # 验证 spoke 文件: 通用区已更新、专属区不变
        spoke_agents = os.path.join(spoke_dir, "AGENTS.md")
        content = open(spoke_agents, encoding="utf-8").read()
        # 通用区已更新为 hub 版本（不再是 spoke 的旧版）
        assert "通用规则" in content
        # 专属区不变
        assert "# 第二部分" in content
        assert "spoke 专属区域内容" in content

    def test_reject_non_writable_items(self, tmpdir):
        """用例4: 收到最新/缺件/结构异常项 → 拒绝写入。"""
        hub_dir, _ = _make_hub_spoke(tmpdir, structure_error_files={"AGENTS.md"})

        from webapp.service import apply_general

        # 尝试写入最新项(CLAIDE.md 默认一致)
        result = apply_general(hub_dir, [{"spoke_name": "产品规划", "file_name": "CLAUDE.md"}])
        assert result[0]["success"] is False
        assert "拒绝" in result[0]["error"] or "不可写" in result[0]["error"]

        # 尝试写入结构异常项
        result = apply_general(hub_dir, [{"spoke_name": "产品规划", "file_name": "AGENTS.md"}])
        assert result[0]["success"] is False


class TestScanLessons:
    """用例5: scan_lessons_up / scan_lessons_down 状态分类正确"""

    def test_scan_up_and_down(self, tmpdir):
        """上行: [↑] 候选分类正确; 下行: new_in_hub/spoke_only 分类正确。"""
        import textwrap
        up_marker_spoke_cl = textwrap.dedent("""\
            # 审查清单

            # 第一部分
            通用审查项。

            # 第二部分

            - **L1 · 符号方向**:hub 版本。
            - **L14 · 新教训(项目) [↑]**:spoke 新增的教训，请求上行。
        """)
        hub_dir, spoke_dir = _make_hub_spoke(tmpdir, spoke_extra={
            "审查清单.md": up_marker_spoke_cl,
        })

        from webapp.service import scan_lessons_up, scan_lessons_down

        # 上行
        up_results = scan_lessons_up(hub_dir)
        spoke_up = [r for r in up_results if r["spoke_name"] == "产品规划"]
        assert len(spoke_up) == 1
        assert spoke_up[0]["state"] in ("new", "update")
        assert spoke_up[0]["can_apply"] is True

        # 下行
        down_results = scan_lessons_down(hub_dir)
        spoke_down = [r for r in down_results if r["spoke_name"] == "产品规划"]
        # hub 有 L1/L2，spoke 有 L1/L14 → L2 是 new_in_hub
        new_items = [r for r in spoke_down if r["state"] == "new_in_hub"]
        assert len(new_items) >= 1
        spoke_only = [r for r in spoke_down if r["state"] == "spoke_only"]
        assert len(spoke_only) >= 1  # L14 是 spoke_only


class TestApplyLessons:
    """用例6: apply_lessons_up 剥 [↑]; apply_lessons_down 按 L 号插入"""

    def test_apply_up_strips_marker(self, tmpdir):
        """上行写入 hub → hub 不含 [↑], L 号正确。"""
        import textwrap
        up_marker_spoke_cl = textwrap.dedent("""\
            # 审查清单

            # 第一部分
            通用审查项。

            # 第二部分

            - **L1 · 符号方向**:hub 版本。
            - **L14 · 新教训(项目) [↑]**:spoke 新增的教训，请求上行。
        """)
        hub_dir, _ = _make_hub_spoke(tmpdir, spoke_extra={
            "审查清单.md": up_marker_spoke_cl,
        })

        from webapp.service import scan_lessons_up, apply_lessons_up

        # 先扫描取候选
        up_results = scan_lessons_up(hub_dir)
        candidates = [r for r in up_results if r["can_apply"]]
        assert len(candidates) >= 1

        # 写入
        apply_result = apply_lessons_up(hub_dir, [{
            "spoke_name": candidates[0]["spoke_name"],
            "l_number": candidates[0]["l_number"],
        }])
        assert apply_result[0]["success"] is True

        # 验证 hub 不含 [↑]
        hub_cl = os.path.join(hub_dir, "审查清单.md")
        content = open(hub_cl, encoding="utf-8").read()
        assert "[↑]" not in content
        assert "L14" in content
        assert "spoke 新增的教训" in content

    def test_apply_down_inserts_correctly(self, tmpdir):
        """下行写入 spoke → L 号正确插入，spoke 专属保留。"""
        import textwrap
        spoke_only_cl = textwrap.dedent("""\
            # 审查清单

            # 第一部分
            通用审查项。

            # 第二部分

            - **L1 · 符号方向**:hub 版本。
            - **L100 · Spoke 专属**:只有这个 spoke 有。
        """)
        hub_dir, spoke_dir = _make_hub_spoke(tmpdir, spoke_extra={
            "审查清单.md": spoke_only_cl,
        })

        from webapp.service import scan_lessons_down, apply_lessons_down

        # 扫描 → L2 应出现为 new_in_hub
        down_results = scan_lessons_down(hub_dir)
        spoke_items = [r for r in down_results if r["spoke_name"] == "产品规划"]
        new_items = [r for r in spoke_items if r["state"] == "new_in_hub"]
        assert len(new_items) >= 1

        # 写入第一个 new_in_hub 项
        apply_result = apply_lessons_down(hub_dir, [{
            "spoke_name": "产品规划",
            "l_number": new_items[0]["l_number"],
        }])
        assert apply_result[0]["success"] is True

        # 验证 spoke: L2 插入, L100 保留
        spoke_cl = os.path.join(spoke_dir, "审查清单.md")
        content = open(spoke_cl, encoding="utf-8").read()
        assert "L2" in content
        assert "L100" in content
        assert "Spoke 专属" in content
