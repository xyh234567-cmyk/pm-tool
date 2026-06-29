"""教训比对器 · lesson_differ
up_diff: spoke [↑] 候选 vs hub 教训列表。
down_diff: hub 教训列表 vs spoke 教训列表。
"""
import difflib
from dataclasses import dataclass, field
from enum import Enum

from app.lesson_parser import Lesson


class UpState(str, Enum):
    NEW = "new"
    UPDATE = "update"
    ALREADY_SYNCED = "already_synced"
    CONFLICT = "conflict"


class DownState(str, Enum):
    NEW_IN_HUB = "new_in_hub"
    CONTENT_CHANGED = "content_changed"
    UP_TO_DATE = "up_to_date"
    SPOKE_ONLY = "spoke_only"


@dataclass
class UpCandidate:
    spoke_name: str
    lesson: Lesson


@dataclass
class UpDiffItem:
    spoke_name: str
    lesson: Lesson
    state: UpState
    hub_lesson: Lesson | None = None
    diff_text: str | None = None
    conflicting: list[tuple[str, Lesson]] | None = None


@dataclass
class DownDiffItem:
    lesson: Lesson
    state: DownState
    spoke_lesson: Lesson | None = None
    diff_text: str | None = None


def up_diff(
    hub_lessons: list[Lesson],
    candidates: list[UpCandidate],
) -> list[UpDiffItem]:
    """上行比对: [↑] 候选 vs hub 教训列表。

    先按单 spoke 做 new/update/already_synced，再全量扫描 conflict。
    """
    if not candidates:
        return []

    hub_map: dict[int, Lesson] = {l.l_number: l for l in hub_lessons}

    results: list[UpDiffItem] = []

    # 第一遍: 单 spoke 判定
    for c in candidates:
        hub_lesson = hub_map.get(c.lesson.l_number)
        if hub_lesson is None:
            results.append(UpDiffItem(
                spoke_name=c.spoke_name,
                lesson=c.lesson,
                state=UpState.NEW,
            ))
        elif _lesson_text_eq(c.lesson, hub_lesson):
            results.append(UpDiffItem(
                spoke_name=c.spoke_name,
                lesson=c.lesson,
                state=UpState.ALREADY_SYNCED,
                hub_lesson=hub_lesson,
            ))
        else:
            diff_text = _unified_diff(hub_lesson.raw_lines, c.lesson.raw_lines)
            results.append(UpDiffItem(
                spoke_name=c.spoke_name,
                lesson=c.lesson,
                state=UpState.UPDATE,
                hub_lesson=hub_lesson,
                diff_text=diff_text,
            ))

    # 第二遍: conflict 检测
    # 按 L 号分组，检查同一 L 号有多个 different spoke
    by_l: dict[int, list[int]] = {}  # L 号 → results 索引列表
    for i, r in enumerate(results):
        ln = r.lesson.l_number
        if r.state in (UpState.NEW, UpState.UPDATE):
            by_l.setdefault(ln, []).append(i)

    for ln, indices in by_l.items():
        if len(indices) >= 2:
            # 检查是否文本各不相同
            texts = set()
            for idx in indices:
                texts.add(_lesson_text_key(results[idx].lesson))
            if len(texts) >= 2:
                # 全部标为 conflict
                for idx in indices:
                    r = results[idx]
                    conflicting = [
                        (results[j].spoke_name, results[j].lesson)
                        for j in indices if j != idx
                    ]
                    r.state = UpState.CONFLICT
                    r.conflicting = conflicting

    return results


def down_diff(
    hub_lessons: list[Lesson],
    spoke_lessons: list[Lesson],
) -> list[DownDiffItem]:
    """下行比对: hub 教训列表 vs spoke 教训列表。"""
    hub_map: dict[int, Lesson] = {l.l_number: l for l in hub_lessons}
    spoke_map: dict[int, Lesson] = {l.l_number: l for l in spoke_lessons}

    results: list[DownDiffItem] = []

    for hub_l in hub_lessons:
        spoke_l = spoke_map.get(hub_l.l_number)
        if spoke_l is None:
            results.append(DownDiffItem(
                lesson=hub_l,
                state=DownState.NEW_IN_HUB,
            ))
        elif _lesson_text_eq(hub_l, spoke_l):
            results.append(DownDiffItem(
                lesson=hub_l,
                state=DownState.UP_TO_DATE,
                spoke_lesson=spoke_l,
            ))
        else:
            diff_text = _unified_diff(spoke_l.raw_lines, hub_l.raw_lines)
            results.append(DownDiffItem(
                lesson=hub_l,
                state=DownState.CONTENT_CHANGED,
                spoke_lesson=spoke_l,
                diff_text=diff_text,
            ))

    for spoke_l in spoke_lessons:
        if spoke_l.l_number not in hub_map:
            results.append(DownDiffItem(
                lesson=spoke_l,
                state=DownState.SPOKE_ONLY,
                spoke_lesson=spoke_l,
            ))

    return results


def _lesson_text_key(lesson: Lesson) -> str:
    return "".join(lesson.raw_lines).replace(" [↑]", "")


def _lesson_text_eq(a: Lesson, b: Lesson) -> bool:
    return _lesson_text_key(a) == _lesson_text_key(b)


def _unified_diff(a_lines: list[str], b_lines: list[str]) -> str:
    a_s = [line.rstrip("\n") for line in a_lines]
    b_s = [line.rstrip("\n") for line in b_lines]
    diff = difflib.unified_diff(a_s, b_s, fromfile="hub", tofile="spoke", lineterm="")
    return "\n".join(diff)
