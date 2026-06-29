"""比对器 · differ
判定 spoke 通用区是否落后于 hub，产出 unified diff。
只比通用区，专属区不读不比。用 difflib 标准库。
"""
import difflib
from dataclasses import dataclass

from app.constants import DiffState
from app.splitter import SplitResult, SplitStatus


@dataclass
class DiffResult:
    state: DiffState
    diff_text: str | None = None


def diff_general(hub: SplitResult, spoke: SplitResult) -> DiffResult:
    """比对 hub 和 spoke 的通用区。

    Args:
        hub: hub 母版文件的切分结果(须 ok)。
        spoke: spoke 副本的切分结果(须 ok)。

    Returns:
        DiffResult: 比对结果。
    """
    # 任一方结构异常
    if hub.status == SplitStatus.STRUCTURE_ERROR or spoke.status == SplitStatus.STRUCTURE_ERROR:
        return DiffResult(state=DiffState.STRUCTURE_ERROR)

    # 只比通用区
    hub_general = hub.general
    spoke_general = spoke.general

    if hub_general == spoke_general:
        return DiffResult(state=DiffState.UP_TO_DATE)

    diff_text = _unified_diff(spoke_general, hub_general)
    return DiffResult(state=DiffState.OUTDATED, diff_text=diff_text)


def _unified_diff(a_lines: list[str], b_lines: list[str]) -> str:
    """生成 unified diff 文本，无多余空行。

    a = spoke(旧), b = hub(新)。
    """
    # 去尾换行再喂 difflib，避免行尾 \n 与 lineterm="" 叠加产生空行
    a_stripped = [line.rstrip('\n') for line in a_lines]
    b_stripped = [line.rstrip('\n') for line in b_lines]
    diff = difflib.unified_diff(
        a_stripped,
        b_stripped,
        fromfile="spoke",
        tofile="hub",
        lineterm="",
    )
    return "\n".join(diff)
