"""教训应用器 · lesson_applier
write_hub: 上行 apply——插入/替换 hub 审查清单.md 第二部分条目。
write_spoke: 下行 apply——插入 spoke 审查清单.md 第二部分条目。
"""
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.lesson_parser import parse_lessons, Lesson
from app.splitter import split_file


@dataclass
class ApplyResult:
    success: bool
    backup_path: str | None = None
    error: str = ""


ANCHOR = "# 第二部分"


def write_hub(
    hub_path: str,
    lesson: Lesson,
    mode: Literal["insert", "replace"],
    dry_run: bool = True,
) -> ApplyResult:
    """上行：向 hub 审查清单.md 写入一条教训。

    Args:
        hub_path: hub 审查清单.md 绝对路径。
        lesson: 要写入的条目（调用方已剥除 [↑]）。
        mode: "insert"（新条目）或 "replace"（更新已有条目）。
        dry_run: True 时不写文件。
    """
    if dry_run:
        return ApplyResult(success=True)

    try:
        with open(hub_path, encoding="utf-8") as f:
            all_lines = f.readlines()
    except OSError as e:
        return ApplyResult(success=False, error=f"读取 hub 失败: {e}")

    cfg = {"general_scope": "before_anchor", "boundary_anchor": ANCHOR}
    split = split_file(all_lines, cfg)

    if split.status.value == "structure_error" or not split.private:
        return ApplyResult(success=False, error="hub 结构异常，无法定位第二部分")

    private_lines = split.private

    if mode == "insert":
        updated_private = _insert_in_l_order(private_lines, lesson)
    else:
        updated_private = _replace_in_private(private_lines, lesson)

    if updated_private is None:
        return ApplyResult(success=False, error=f"replace 失败: L{lesson.l_number} 未找到")

    new_content = split.general + updated_private

    # 备份
    backup_path = _backup(hub_path)
    if backup_path is None:
        return ApplyResult(success=False, error="备份失败: 无法创建备份文件")

    try:
        with open(hub_path, "w", encoding="utf-8") as f:
            f.writelines(new_content)
    except OSError as e:
        return ApplyResult(success=False, error=f"写入 hub 失败: {e}", backup_path=backup_path)

    return ApplyResult(success=True, backup_path=backup_path)


def write_spoke(
    spoke_path: str,
    lesson: Lesson,
    dry_run: bool = True,
) -> ApplyResult:
    """下行：在 spoke 审查清单.md 第二部分按 L 号序插入一条教训。

    Args:
        spoke_path: spoke 审查清单.md 绝对路径。
        lesson: hub 侧的条目（无 [↑]）。
        dry_run: True 时不写文件。
    """
    if dry_run:
        return ApplyResult(success=True)

    try:
        with open(spoke_path, encoding="utf-8") as f:
            all_lines = f.readlines()
    except OSError as e:
        return ApplyResult(success=False, error=f"读取 spoke 失败: {e}")

    cfg = {"general_scope": "before_anchor", "boundary_anchor": ANCHOR}
    split = split_file(all_lines, cfg)

    if split.status.value == "structure_error" or not split.private:
        return ApplyResult(success=False, error="spoke 结构异常，无法定位第二部分")

    # 冲突检测
    existing = parse_lessons(split.private)
    for e in existing:
        if e.l_number == lesson.l_number:
            return ApplyResult(success=False, error=f"insert_conflict: L{lesson.l_number} 已存在")

    updated_private = _insert_in_l_order(split.private, lesson)

    new_content = split.general + updated_private

    # 备份
    backup_path = _backup(spoke_path)
    if backup_path is None:
        return ApplyResult(success=False, error="备份失败: 无法创建备份文件")

    try:
        with open(spoke_path, "w", encoding="utf-8") as f:
            f.writelines(new_content)
    except OSError as e:
        return ApplyResult(success=False, error=f"写入 spoke 失败: {e}", backup_path=backup_path)

    return ApplyResult(success=True, backup_path=backup_path)


# ---- 内部工具函数 ----

def _insert_in_l_order(
    private_lines: list[str],
    new_lesson: Lesson,
) -> list[str]:
    """在第二部分行列表中，把 new_lesson.raw_lines 插到正确 L 号位置。"""
    lessons = parse_lessons(private_lines)

    # 找插入位置：最后一个 l_number < new_lesson.l_number 的条目之后
    insert_after_idx = -1  # -1 表示插在最前面（锚点行之后）
    for i, ls in enumerate(lessons):
        if ls.l_number < new_lesson.l_number:
            insert_after_idx = i
        else:
            break

    # 重建 private_lines
    result: list[str] = []

    if insert_after_idx == -1:
        # 插在锚点行之后、所有教训之前
        i = 0
        # 输出锚点行
        while i < len(private_lines) and not private_lines[i].startswith("- **L"):
            result.append(private_lines[i])
            i += 1
        # 空行
        if result and result[-1].strip() == "":
            pass
        else:
            result.append("\n")
        result.extend(new_lesson.raw_lines)
        result.append("\n")
        result.extend(private_lines[i:])
    else:
        # 找到 insert_after_idx 条目的结尾行
        target_lesson = lessons[insert_after_idx]
        target_start = private_lines.index(target_lesson.raw_lines[0])
        target_end = target_start + len(target_lesson.raw_lines)

        result.extend(private_lines[:target_end])
        result.extend(new_lesson.raw_lines)
        result.append("\n")
        result.extend(private_lines[target_end:])

    return result


def _replace_in_private(
    private_lines: list[str],
    new_lesson: Lesson,
) -> list[str] | None:
    """替换同 L 号条目，返回新 private_lines 或 None(未找到)。"""
    lessons = parse_lessons(private_lines)
    for existing in lessons:
        if existing.l_number == new_lesson.l_number:
            start = private_lines.index(existing.raw_lines[0])
            end = start + len(existing.raw_lines)
            return (
                private_lines[:start]
                + new_lesson.raw_lines
                + private_lines[end:]
            )
    return None


def _backup(file_path: str) -> str | None:
    """创建备份文件，返回备份路径或 None。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(file_path)
    backup_path = os.path.join(os.path.dirname(file_path), f"{base}.bak.{ts}")
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except (OSError, IOError):
        return None
