"""应用器 · applier
对人选中的 outdated 项，备份并替换通用区。
严守 red_lines：不碰专属区、不删内容、未备份不写、不回写 hub、结构异常不写。
"""
import os
import shutil
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from app.splitter import split_file, SplitResult, SplitStatus
from app.constants import DiffState, MANAGED_FILE_MAP


@dataclass
class ApplyResult:
    success: bool
    backup_path: str | None = None
    error: str = ""


def apply_file(
    hub_dir: str,
    spoke_path: str,
    file_name: str,
    hub_general: list[str],
    spoke_private: list[str],
    dry_run: bool = True,
) -> ApplyResult:
    """应用通用区更新:备份 → 写回。

    - whole_file(CLAUDE.md): 直接用 hub 整份。
    - before_anchor: hub 通用区 + spoke 原专属区原样拼回。

    Args:
        hub_dir: hub 目录(用于读取 hub 文件——只读)。
        spoke_path: spoke 文件绝对路径。
        file_name: 文件名(CLAUDE.md / AGENTS.md / 审查清单.md)。
        hub_general: hub 文件的通用区。
        spoke_private: spoke 文件的专属区(原样保留)。
        dry_run: True 时不写文件，不备份。

    Returns:
        ApplyResult: 操作结果。
    """
    cfg = MANAGED_FILE_MAP.get(file_name)

    if cfg is None:
        return ApplyResult(success=False, error=f"未受管文件: {file_name}")

    # dry-run: 不产生任何文件写入
    if dry_run:
        return ApplyResult(success=True, backup_path=None)

    # 构造新内容
    if cfg.general_scope == "whole_file":
        new_content = hub_general
    else:
        # before_anchor: hub 通用区 + spoke 原专属区原样拼回
        new_content = hub_general + spoke_private

    # 先备份
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{file_name}.bak.{timestamp}"
    backup_path = os.path.join(os.path.dirname(spoke_path), backup_name)

    try:
        shutil.copy2(spoke_path, backup_path)
    except (OSError, IOError) as e:
        return ApplyResult(
            success=False,
            error=f"备份失败: {e}",
            backup_path=None,
        )

    # 写入新内容
    try:
        with open(spoke_path, "w", encoding="utf-8") as f:
            f.writelines(new_content)
    except (OSError, IOError) as e:
        return ApplyResult(
            success=False,
            error=f"写入失败: {e}",
            backup_path=backup_path,
        )

    return ApplyResult(success=True, backup_path=backup_path)
