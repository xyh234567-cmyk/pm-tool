"""教训解析器 · lesson_parser
把审查清单.md 第二部分的文本行解析为 list[Lesson]。
格式: - **L{n} · 标题(来源)**:内容。
"""
import re
from dataclasses import dataclass, field

# 起始行匹配: 顶格的 "- **L{digits}"
_LESSON_START_RE = re.compile(r"^- \*\*L(\d+)")


@dataclass
class Lesson:
    l_number: int
    raw_lines: list[str]
    has_up_marker: bool = False


def parse_lessons(private_lines: list[str]) -> list[Lesson]:
    """解析第二部分文本行为教训条目列表。

    Args:
        private_lines: splitter 返回的 SplitResult.private。

    Returns:
        list[Lesson]: 按出现顺序排列。
    """
    lessons: list[Lesson] = []
    current_lines: list[str] = []
    current_has_marker = False
    current_l_number: int | None = None

    def _flush():
        nonlocal current_l_number
        if current_l_number is not None and current_lines:
            lessons.append(Lesson(
                l_number=current_l_number,
                raw_lines=list(current_lines),
                has_up_marker=current_has_marker,
            ))
        current_l_number = None

    for line in private_lines:
        # 跳过锚点行本身
        if line.startswith("# 第二部分"):
            continue

        m = _LESSON_START_RE.match(line)
        if m:
            _flush()
            current_lines = [line]
            current_l_number = int(m.group(1))
            current_has_marker = "[↑]" in line
        else:
            if current_l_number is not None:
                current_lines.append(line)
            # 否则: 锚点行后的散文，不属于任何条目，忽略

    _flush()
    return lessons
