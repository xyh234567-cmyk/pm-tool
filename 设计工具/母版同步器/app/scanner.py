"""扫描器 · scanner
在项目根目录下找出受管 spoke，产出"待处理文件对"清单。
三分法: 三件套齐全(同步) / 缺件提醒(missing_file) / 无关目录(静默跳过)。
"""
import os
from dataclasses import dataclass

from app.constants import (
    SCAN_HUB_DIRNAME,
    SPOKE_REQUIRED_FILES,
    EXCLUDE_DIRNAMES,
    EXCLUDE_HIDDEN,
    MANAGED_FILES,
    INCOMPLETE_MARKER_FILES,
    DiffState,
)


@dataclass
class SpokeFilePair:
    spoke_name: str
    file_name: str
    hub_path: str
    spoke_path: str
    state: DiffState = DiffState.OUTDATED
    error_reason: str = ""


def scan(hub_dir: str) -> list[SpokeFilePair]:
    """扫描项目根目录，找出受管 spoke 并生成文件对清单。

    遍历 root 直接子目录(排除隐藏/exclude_dirnames)，按完整度三分:
    - 三件套齐全 → 受管 spoke: 每个 managed_files 生成文件对。
    - 不全但含 marker_file(审查清单.md) → 缺件提醒: 每个缺失文件产出
      missing_file, present 文件不同步。
    - 既非三件套齐全又无 marker_file → 静默跳过。

    Args:
        hub_dir: hub 目录的绝对路径(即 设计工具/)。

    Returns:
        list[SpokeFilePair]: 每个 spoke × 每个 managed_file 一个文件对。
    """
    if not os.path.isdir(hub_dir):
        raise FileNotFoundError(f"hub 目录不存在: {hub_dir}")

    root = os.path.dirname(hub_dir)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"项目根目录不存在: {root}")

    pairs: list[SpokeFilePair] = []

    try:
        entries = os.listdir(root)
    except OSError as e:
        raise OSError(f"无法读取根目录 {root}: {e}")

    for entry in sorted(entries):
        entry_path = os.path.join(root, entry)

        if not os.path.isdir(entry_path):
            continue
        if EXCLUDE_HIDDEN and entry.startswith('.'):
            continue
        if entry in EXCLUDE_DIRNAMES:
            continue

        present, missing = _check_files(entry_path)

        if len(missing) == 0:
            # 三件套齐全 → 生成全部文件对
            for mf in MANAGED_FILES:
                hub_file = os.path.join(hub_dir, mf.name)
                spoke_file = os.path.join(entry_path, mf.name)
                pairs.append(SpokeFilePair(
                    spoke_name=entry,
                    file_name=mf.name,
                    hub_path=hub_file,
                    spoke_path=spoke_file,
                ))

        elif _has_marker(entry_path):
            # 不全但含 marker_file → 只为缺失文件报 missing_file
            for fname in missing:
                hub_file = os.path.join(hub_dir, fname)
                spoke_file = os.path.join(entry_path, fname)
                pairs.append(SpokeFilePair(
                    spoke_name=entry,
                    file_name=fname,
                    hub_path=hub_file,
                    spoke_path=spoke_file,
                    state=DiffState.MISSING_FILE,
                    error_reason="spoke 缺少此受管文件: " + fname,
                ))

        # 否则: 既非三件套齐全、又无 marker_file → 静默跳过

    return pairs


def _check_files(dir_path: str) -> tuple[list[str], list[str]]:
    """返回 (present列表, missing列表)。"""
    present = []
    missing = []
    for fname in SPOKE_REQUIRED_FILES:
        if os.path.isfile(os.path.join(dir_path, fname)):
            present.append(fname)
        else:
            missing.append(fname)
    return present, missing


def _has_marker(dir_path: str) -> bool:
    """检查目录是否包含任一 marker(审查清单.md 或 AGENTS.md)。"""
    for marker in INCOMPLETE_MARKER_FILES:
        if os.path.isfile(os.path.join(dir_path, marker)):
            return True
    return False
