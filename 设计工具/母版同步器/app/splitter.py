"""分区切分器 · splitter
按锚点把文件文本切成「通用区/专属区」。
CLAUDE.md(whole_file): 整份为通用区。
AGENTS.md / 审查清单.md(before_anchor): 按 "# 第二部分" 切分。
锚点缺失/重复 → structure_error，不猜切分点。
"""
from dataclasses import dataclass, field

from app.constants import SplitStatus


@dataclass
class SplitResult:
    status: SplitStatus
    general: list[str] = field(default_factory=list)
    private: list[str] = field(default_factory=list)


def split_file(lines: list[str], cfg: dict) -> SplitResult:
    """对一份文件的文本行做分区切分。

    Args:
        lines: 文件全部行(含换行符)。
        cfg: 文件配置，含 general_scope 和 boundary_anchor。

    Returns:
        SplitResult: 切分结果。structure_error 时 general/private 均为空。
    """
    scope = cfg["general_scope"]
    anchor = cfg.get("boundary_anchor")

    if scope == "whole_file":
        return SplitResult(status=SplitStatus.OK, general=list(lines), private=[])

    if scope == "before_anchor":
        return _split_before_anchor(lines, anchor)

    # 未知 scope → 安全跳过
    return SplitResult(status=SplitStatus.STRUCTURE_ERROR)


def _split_before_anchor(lines: list[str], anchor: str) -> SplitResult:
    """找锚点行，切分通用区/专属区。

    规则(照搬 分区边界.yaml):
    - line_startswith: 行以 anchor 前缀开头才算锚点。
    - strip_leading_whitespace=false: 顶格匹配，行首有空白不算。
    - expect_exactly_one=true: 恰好 1 个 → ok；0 或 >1 → structure_error。
    """
    anchor_indices: list[int] = []
    for i, line in enumerate(lines):
        if line.startswith(anchor):
            anchor_indices.append(i)

    if len(anchor_indices) != 1:
        return SplitResult(status=SplitStatus.STRUCTURE_ERROR)

    idx = anchor_indices[0]
    general = lines[:idx]
    private = lines[idx:]
    return SplitResult(status=SplitStatus.OK, general=general, private=private)
