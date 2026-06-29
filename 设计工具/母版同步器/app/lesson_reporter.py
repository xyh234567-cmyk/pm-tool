"""教训呈现器 · lesson_reporter
把上行/下行比对结果汇总输出，落 Markdown 报告。
"""
import os
from datetime import datetime
from dataclasses import dataclass, field

from app.lesson_differ import UpDiffItem, DownDiffItem, UpState, DownState


def print_terminal_up(items: list[UpDiffItem]) -> None:
    """终端输出上行结果。"""
    if not items:
        print("无上行候选。")
        return

    by_spoke: dict[str, list[UpDiffItem]] = {}
    for r in items:
        by_spoke.setdefault(r.spoke_name, []).append(r)

    for spoke_name, group in sorted(by_spoke.items()):
        print(f"\n{'='*60}")
        print(f"  {spoke_name}")
        print(f"{'='*60}")
        for r in group:
            label = _up_label(r.state)
            print(f"  {label} L{r.lesson.l_number}")
            if r.state == UpState.NEW:
                text = "".join(r.lesson.raw_lines).rstrip()
                print(f"    {text}")
            elif r.state == UpState.UPDATE:
                print(f"    建议更新:")
                for line in (r.diff_text or "").split("\n"):
                    print(f"      {line}")
            elif r.state == UpState.ALREADY_SYNCED:
                print(f"    已同步，可移除 [↑] 标记")
            elif r.state == UpState.CONFLICT:
                print(f"    ❗冲突: 多个 spoke 对此 L 号有不同提案")
                for sn, _ in (r.conflicting or []):
                    print(f"      - {sn}")
                text = "".join(r.lesson.raw_lines).rstrip()
                print(f"    {text}")


def print_terminal_down(by_spoke: dict[str, list[DownDiffItem]]) -> None:
    """终端输出下行结果。"""
    if not by_spoke:
        print("无受管 spoke。")
        return

    any_action = False
    for spoke_name, items in sorted(by_spoke.items()):
        new_items = [r for r in items if r.state == DownState.NEW_IN_HUB]
        changed = [r for r in items if r.state == DownState.CONTENT_CHANGED]
        if not new_items and not changed:
            continue
        any_action = True
        print(f"\n{'='*60}")
        print(f"  {spoke_name}")
        print(f"{'='*60}")
        for r in new_items:
            print(f"  ➕ L{r.lesson.l_number} (新增)")
            text = "".join(r.lesson.raw_lines).rstrip()
            print(f"    {text}")
        for r in changed:
            print(f"  📝 L{r.lesson.l_number} (内容变更·仅提示·不写入)")
            for line in (r.diff_text or "").split("\n"):
                print(f"      {line}")

    if not any_action:
        print("所有 spoke 均已最新。")


def write_markdown_up(
    items: list[UpDiffItem],
    hub_dir: str,
    applied: list | None = None,
) -> str:
    """写上行 Markdown 报告，返回路径。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"母版同步报告-教训上行-{ts}.md"
    path = os.path.join(hub_dir, filename)

    lines = [f"# 母版同步报告 · 教训上行 · {ts}", "", f"生成时间: {_fmt_ts(ts)}", ""]
    if not items:
        lines.append("> 无上行候选。")
    else:
        by_spoke = _group_up(items)
        for spoke_name, group in sorted(by_spoke.items()):
            lines.append(f"## {spoke_name}")
            lines.append("")
            for r in group:
                label = _up_label(r.state)
                lines.append(f"- {label} **L{r.lesson.l_number}**")
                if r.state == UpState.NEW:
                    lines.append(f"  ```")
                    text = "".join(r.lesson.raw_lines).rstrip()
                    lines.append(f"  {text}")
                    lines.append(f"  ```")
                elif r.state == UpState.UPDATE:
                    lines.append(f"  ```diff")
                    for line in (r.diff_text or "").split("\n"):
                        lines.append(f"  {line}")
                    lines.append(f"  ```")
                elif r.state == UpState.CONFLICT:
                    for sn, _ in (r.conflicting or []):
                        lines.append(f"  - 与 {sn} 冲突")
            lines.append("")

    if applied:
        lines.append("## 本次写入记录")
        for item in applied:
            lines.append(f"- L{item.lesson.l_number}: {item.spoke_name}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def write_markdown_down(
    by_spoke: dict[str, list[DownDiffItem]],
    hub_dir: str,
    applied: list | None = None,
) -> str:
    """写下行 Markdown 报告，返回路径。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"母版同步报告-教训下行-{ts}.md"
    path = os.path.join(hub_dir, filename)

    lines = [f"# 母版同步报告 · 教训下行 · {ts}", "", f"生成时间: {_fmt_ts(ts)}", ""]
    for spoke_name, items in sorted(by_spoke.items()):
        lines.append(f"## {spoke_name}")
        lines.append("")
        for r in items:
            label = _down_label(r.state)
            lines.append(f"- {label} **L{r.lesson.l_number}**")
            if r.state == DownState.NEW_IN_HUB:
                lines.append(f"  ```")
                text = "".join(r.lesson.raw_lines).rstrip()
                lines.append(f"  {text}")
                lines.append(f"  ```")
            elif r.state == DownState.CONTENT_CHANGED:
                lines.append(f"  *(仅提示·不写入)*")
                lines.append(f"  ```diff")
                for line in (r.diff_text or "").split("\n"):
                    lines.append(f"  {line}")
                lines.append(f"  ```")
        lines.append("")

    if applied:
        lines.append("## 本次写入记录")
        for item in applied:
            lines.append(f"- L{item.lesson.l_number} → {item.spoke_name}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _group_up(items):
    d: dict[str, list] = {}
    for r in items:
        d.setdefault(r.spoke_name, []).append(r)
    return d


def _up_label(state: UpState) -> str:
    return {
        UpState.NEW: "➕",
        UpState.UPDATE: "📝",
        UpState.ALREADY_SYNCED: "✅",
        UpState.CONFLICT: "❌",
    }.get(state, "❓")


def _down_label(state: DownState) -> str:
    return {
        DownState.NEW_IN_HUB: "➕",
        DownState.CONTENT_CHANGED: "📝",
        DownState.UP_TO_DATE: "✅",
        DownState.SPOKE_ONLY: "🔒",
    }.get(state, "❓")


def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.strptime(ts, "%Y%m%d-%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts
