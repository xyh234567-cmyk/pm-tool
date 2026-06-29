"""编排层 · service
把 CLI main.py 的流水线逻辑翻译为返回结构化数据，不 print、不 input。
apply 函数必须服务端重新校验——绝不因前端传了就写。
"""
import os
from app.constants import DiffState, SplitStatus, MANAGED_FILE_MAP
from app.scanner import scan
from app.splitter import split_file
from app.differ import diff_general
from app.applier import apply_file
from app.lesson_parser import parse_lessons, Lesson
from app.lesson_differ import up_diff, down_diff, UpCandidate, UpState, DownState
from app.lesson_applier import write_hub, write_spoke

ANCHOR = "# 第二部分"


def scan_general(hub_dir: str) -> list[dict]:
    """扫描各 spoke 的通用区文件状态，返回结构化结果列表。"""
    pairs = scan(hub_dir)
    results: list[dict] = []

    for pair in pairs:
        if pair.state == DiffState.MISSING_FILE:
            continue
        cfg = _cfg_for_file(pair.file_name)

        try:
            with open(pair.hub_path, encoding="utf-8") as f:
                hub_lines = f.readlines()
        except OSError:
            results.append({"spoke_name": pair.spoke_name, "file_name": pair.file_name,
                "state": "missing_file", "diff_text": "", "can_apply": False,
                "label": f"{pair.spoke_name}/{pair.file_name} - 无法读取 hub"})
            continue

        try:
            with open(pair.spoke_path, encoding="utf-8") as f:
                spoke_lines = f.readlines()
        except OSError:
            results.append({"spoke_name": pair.spoke_name, "file_name": pair.file_name,
                "state": "missing_file", "diff_text": "", "can_apply": False,
                "label": f"{pair.spoke_name}/{pair.file_name} - 无法读取 spoke"})
            continue

        hub_split = split_file(hub_lines, cfg)
        spoke_split = split_file(spoke_lines, cfg)

        if hub_split.status == SplitStatus.STRUCTURE_ERROR:
            results.append({"spoke_name": pair.spoke_name, "file_name": pair.file_name,
                "state": "structure_error", "diff_text": "", "can_apply": False,
                "label": f"{pair.spoke_name}/{pair.file_name} - hub 结构异常"})
            continue

        if spoke_split.status == SplitStatus.STRUCTURE_ERROR:
            results.append({"spoke_name": pair.spoke_name, "file_name": pair.file_name,
                "state": "structure_error", "diff_text": "", "can_apply": False,
                "label": f"{pair.spoke_name}/{pair.file_name} - spoke 结构异常"})
            continue

        diff_result = diff_general(hub_split, spoke_split)
        state_str = diff_result.state.value
        can_apply = diff_result.state == DiffState.OUTDATED
        diff_text = diff_result.diff_text or ""
        label = f"{pair.spoke_name}/{pair.file_name}"
        if state_str == "outdated":
            label += " - 过时"
        elif state_str == "up_to_date":
            label += " - 已最新"

        results.append({"spoke_name": pair.spoke_name, "file_name": pair.file_name,
            "state": state_str, "diff_text": diff_text, "can_apply": can_apply, "label": label})

    return results


def apply_general(hub_dir: str, items: list[dict]) -> list[dict]:
    """应用通用区更新: 对每项 re-validate → write。"""
    results: list[dict] = []
    current = scan_general(hub_dir)
    index = {}
    for r in current:
        index[(r["spoke_name"], r["file_name"])] = r
    pairs = scan(hub_dir)
    pair_index = {}
    for p in pairs:
        pair_index[(p.spoke_name, p.file_name)] = p

    for item in items:
        spoke_name = item.get("spoke_name", "")
        file_name = item.get("file_name", "")
        key = (spoke_name, file_name)
        cur = index.get(key)
        if not cur or cur["state"] != "outdated":
            results.append({"success": False, "error": f"拒绝写入: {spoke_name}/{file_name} 非可写态"})
            continue
        pair = pair_index.get(key)
        if pair is None:
            results.append({"success": False, "error": "拒绝写入: 找不到文件对"})
            continue
        cfg = _cfg_for_file(file_name)
        with open(pair.hub_path, encoding="utf-8") as f:
            hub_lines = f.readlines()
        with open(pair.spoke_path, encoding="utf-8") as f:
            spoke_lines = f.readlines()
        hub_split = split_file(hub_lines, cfg)
        spoke_split = split_file(spoke_lines, cfg)
        apply_result = apply_file(hub_dir=hub_dir, spoke_path=pair.spoke_path,
            file_name=file_name, hub_general=hub_split.general,
            spoke_private=spoke_split.private, dry_run=False)
        results.append({"success": apply_result.success, "error": apply_result.error,
            "backup_path": apply_result.backup_path})

    return results


def scan_lessons_up(hub_dir: str) -> list[dict]:
    """扫描所有受管 spoke 的 [↑] 候选。"""
    pairs = scan(hub_dir)
    hub_path = os.path.join(hub_dir, "审查清单.md")
    cfg = {"general_scope": "before_anchor", "boundary_anchor": ANCHOR}
    if not os.path.isfile(hub_path):
        return []
    with open(hub_path, encoding="utf-8") as f:
        hub_lines = f.readlines()
    hub_split = split_file(hub_lines, cfg)
    hub_lessons = parse_lessons(hub_split.private)
    candidates: list[UpCandidate] = []
    for pair in pairs:
        if pair.file_name != "审查清单.md":
            continue
        if not os.path.isfile(pair.spoke_path):
            continue
        with open(pair.spoke_path, encoding="utf-8") as f:
            spoke_lines = f.readlines()
        spoke_split = split_file(spoke_lines, cfg)
        for lesson in parse_lessons(spoke_split.private):
            if lesson.has_up_marker:
                candidates.append(UpCandidate(pair.spoke_name, lesson))
    if not candidates:
        return []

    results: list[dict] = []
    for r in up_diff(hub_lessons, candidates):
        state_str = r.state.value
        can_apply = state_str in ("new", "update")
        results.append({"spoke_name": r.spoke_name, "l_number": r.lesson.l_number,
            "state": state_str, "diff_text": r.diff_text or "", "can_apply": can_apply,
            "label": f"{r.spoke_name} / L{r.lesson.l_number} - {_up_label_zh(r.state)}"})
    return results


def apply_lessons_up(hub_dir: str, items: list[dict]) -> list[dict]:
    """上行写入 hub: re-validate → 剥 [↑] → write_hub。"""
    results: list[dict] = []
    current = scan_lessons_up(hub_dir)
    index: dict = {}
    for r in current:
        index[(r["spoke_name"], r["l_number"])] = r
    hub_path = os.path.join(hub_dir, "审查清单.md")

    for item in items:
        spoke_name = item.get("spoke_name", "")
        l_number = item.get("l_number", 0)
        key = (spoke_name, l_number)
        cur = index.get(key)
        if not cur or not cur["can_apply"]:
            results.append({"success": False, "error": f"拒绝写入: {spoke_name}/L{l_number} 不可写"})
            continue
        # 重新获取原始 lesson
        scfg = {"general_scope": "before_anchor", "boundary_anchor": ANCHOR}
        raw_lesson = None
        for pair in scan(hub_dir):
            if pair.file_name != "审查清单.md" or pair.spoke_name != spoke_name:
                continue
            with open(pair.spoke_path, encoding="utf-8") as f:
                lines = f.readlines()
            for ls in parse_lessons(split_file(lines, scfg).private):
                if ls.l_number == l_number and ls.has_up_marker:
                    raw_lesson = ls
                    break
            break
        if raw_lesson is None:
            results.append({"success": False, "error": f"拒绝写入: L{l_number} 候选不存在"})
            continue
        cleaned = [ln.replace(" [↑]", "") for ln in raw_lesson.raw_lines]
        clean_lesson = Lesson(l_number=raw_lesson.l_number, raw_lines=cleaned, has_up_marker=False)
        mode = "replace" if cur["state"] == "update" else "insert"
        ar = write_hub(hub_path, clean_lesson, mode, dry_run=False)
        results.append({"success": ar.success, "error": ar.error, "backup_path": ar.backup_path})
    return results


def scan_lessons_down(hub_dir: str) -> list[dict]:
    """扫描各 spoke 的下行项。"""
    hub_path = os.path.join(hub_dir, "审查清单.md")
    cfg = {"general_scope": "before_anchor", "boundary_anchor": ANCHOR}
    if not os.path.isfile(hub_path):
        return []
    with open(hub_path, encoding="utf-8") as f:
        hub_lines = f.readlines()
    hub_split = split_file(hub_lines, cfg)
    hub_lessons = parse_lessons(hub_split.private)
    results: list[dict] = []
    for pair in scan(hub_dir):
        if pair.file_name != "审查清单.md":
            continue
        if not os.path.isfile(pair.spoke_path):
            continue
        with open(pair.spoke_path, encoding="utf-8") as f:
            spoke_lines = f.readlines()
        spoke_split = split_file(spoke_lines, cfg)
        spoke_lessons = parse_lessons(spoke_split.private)
        for r in down_diff(hub_lessons, spoke_lessons):
            state_str = r.state.value
            can_apply = state_str == "new_in_hub"
            results.append({"spoke_name": pair.spoke_name, "l_number": r.lesson.l_number,
                "state": state_str, "diff_text": r.diff_text or "", "can_apply": can_apply,
                "label": f"{pair.spoke_name} / L{r.lesson.l_number} - {_down_label_zh(r.state)}"})
    return results


def apply_lessons_down(hub_dir: str, items: list[dict]) -> list[dict]:
    """下行写入 spoke: re-validate → write_spoke。"""
    results: list[dict] = []
    current = scan_lessons_down(hub_dir)
    index: dict = {}
    for r in current:
        index[(r["spoke_name"], r["l_number"])] = r
    pairs = scan(hub_dir)
    for item in items:
        spoke_name = item.get("spoke_name", "")
        l_number = item.get("l_number", 0)
        key = (spoke_name, l_number)
        cur = index.get(key)
        if not cur or not cur["can_apply"]:
            results.append({"success": False, "error": f"拒绝写入: {spoke_name}/L{l_number} 不可写"})
            continue
        spoke_path = None
        for pair in pairs:
            if pair.file_name == "审查清单.md" and pair.spoke_name == spoke_name:
                spoke_path = pair.spoke_path
                break
        if spoke_path is None:
            results.append({"success": False, "error": f"拒绝写入: 找不到 {spoke_name} 的审查清单"})
            continue
        hub_path = os.path.join(hub_dir, "审查清单.md")
        cfg = {"general_scope": "before_anchor", "boundary_anchor": ANCHOR}
        with open(hub_path, encoding="utf-8") as f:
            hub_lines = f.readlines()
        hub_lessons = parse_lessons(split_file(hub_lines, cfg).private)
        target = None
        for ls in hub_lessons:
            if ls.l_number == l_number:
                target = ls
                break
        if target is None:
            results.append({"success": False, "error": f"拒绝写入: hub 已无 L{l_number}"})
            continue
        ar = write_spoke(spoke_path, target, dry_run=False)
        results.append({"success": ar.success, "error": ar.error, "backup_path": ar.backup_path})
    return results


def _cfg_for_file(file_name: str) -> dict:
    mf = MANAGED_FILE_MAP.get(file_name)
    if mf is None:
        return {"general_scope": "whole_file", "boundary_anchor": None}
    return {"general_scope": mf.general_scope, "boundary_anchor": mf.boundary_anchor}


def _up_label_zh(state: UpState) -> str:
    return {UpState.NEW: "新增候选", UpState.UPDATE: "更新候选",
        UpState.ALREADY_SYNCED: "已同步", UpState.CONFLICT: "冲突"}.get(state, "未知")


def _down_label_zh(state: DownState) -> str:
    return {DownState.NEW_IN_HUB: "hub 新增", DownState.CONTENT_CHANGED: "内容变更(仅提示)",
        DownState.UP_TO_DATE: "已最新", DownState.SPOKE_ONLY: "spoke 专属"}.get(state, "未知")
