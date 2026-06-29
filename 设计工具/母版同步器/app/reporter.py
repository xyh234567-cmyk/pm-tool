"""呈现器 · reporter
把全部结果汇总输出给人看，并落 Markdown 报告。
终端可读摘要 + Markdown 报告落 hub 根。
"""
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from app.constants import DiffState
from app.scanner import SpokeFilePair
from app.differ import DiffResult


@dataclass
class ReportItem:
    spoke_name: str
    file_name: str
    state: DiffState
    diff_text: str | None = None
    error_reason: str = ""
    backup_path: str | None = None  # 应用后的备份路径


@dataclass
class SyncReport:
    timestamp: str
    items: list[ReportItem] = field(default_factory=list)
    applied: list[ReportItem] = field(default_factory=list)


def build_report(
    pairs_and_diffs: list[tuple[SpokeFilePair, DiffResult | None]],
) -> SyncReport:
    """从文件对和 diff 结果构建报告。

    Args:
        pairs_and_diffs: (SpokeFilePair, DiffResult) 元组列表。
        missing_file 或 structure_error 时 DiffResult 为 None。

    Returns:
        SyncReport: 同步报告。
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = SyncReport(timestamp=timestamp)

    for pair, diff_result in pairs_and_diffs:
        item = ReportItem(
            spoke_name=pair.spoke_name,
            file_name=pair.file_name,
            state=pair.state,
            error_reason=pair.error_reason if pair.state != DiffState.OUTDATED else "",
        )
        if diff_result is not None:
            item.state = diff_result.state
            item.diff_text = diff_result.diff_text
        report.items.append(item)

    return report


def print_terminal(report: SyncReport) -> None:
    """终端可读摘要。"""
    if not report.items:
        print("无受管项目。")
        return

    # 按 spoke 分组
    by_spoke: dict[str, list[ReportItem]] = {}
    for item in report.items:
        by_spoke.setdefault(item.spoke_name, []).append(item)

    for spoke_name, items in sorted(by_spoke.items()):
        print(f"\n{'='*60}")
        print(f"  spoke: {spoke_name}")
        print(f"{'='*60}")
        for item in items:
            icon = _state_icon(item.state)
            print(f"  {icon} {item.file_name}  [{item.state.value}]")
            if item.error_reason:
                print(f"     原因: {item.error_reason}")
            if item.state == DiffState.OUTDATED and item.diff_text:
                print(f"     差异:")
                for line in item.diff_text.split("\n"):
                    print(f"      {line}")
            if item.backup_path:
                print(f"     备份: {item.backup_path}")


def write_markdown(report: SyncReport, hub_dir: str) -> str:
    """写 Markdown 报告到 hub 根，返回报告路径。

    Args:
        report: 同步报告。
        hub_dir: hub 目录绝对路径。

    Returns:
        str: 报告文件的绝对路径。
    """
    filename = f"母版同步报告-{report.timestamp}.md"
    path = os.path.join(hub_dir, filename)

    lines: list[str] = []
    lines.append(f"# 母版同步报告 · {report.timestamp}")
    lines.append("")
    lines.append(f"生成时间: {_format_timestamp(report.timestamp)}")
    lines.append("")

    if not report.items:
        lines.append("> 无受管项目。")
    else:
        by_spoke: dict[str, list[ReportItem]] = {}
        for item in report.items:
            by_spoke.setdefault(item.spoke_name, []).append(item)

        for spoke_name, items in sorted(by_spoke.items()):
            lines.append(f"## {spoke_name}")
            lines.append("")
            for item in items:
                icon = _state_icon(item.state)
                lines.append(f"- {icon} **{item.file_name}** — `{item.state.value}`")
                if item.error_reason:
                    lines.append(f"  - 原因: {item.error_reason}")
                if item.state == DiffState.OUTDATED and item.diff_text:
                    lines.append(f"  - 差异:")
                    lines.append("")
                    lines.append("    ```diff")
                    for line in item.diff_text.split("\n"):
                        lines.append(f"    {line}")
                    lines.append("    ```")
                    lines.append("")
                if item.backup_path:
                    lines.append(f"  - 备份: `{item.backup_path}`")
            lines.append("")

    # applied 节
    if report.applied:
        lines.append("## 本次写入记录")
        lines.append("")
        for item in report.applied:
            lines.append(f"- {item.spoke_name}/{item.file_name}")
            if item.backup_path:
                lines.append(f"  - 备份: `{item.backup_path}`")
            lines.append(f"  - 状态: 通用区已更新")
        lines.append("")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def _state_icon(state: DiffState) -> str:
    icons = {
        DiffState.UP_TO_DATE: "✅",
        DiffState.OUTDATED: "⚠️",
        DiffState.STRUCTURE_ERROR: "❌",
        DiffState.MISSING_FILE: "📭",
    }
    return icons.get(state, "❓")


def _format_timestamp(ts: str) -> str:
    """YYYYMMDD-HHMMSS → 可读格式。"""
    try:
        dt = datetime.strptime(ts, "%Y%m%d-%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts
