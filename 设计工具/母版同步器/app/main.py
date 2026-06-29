"""母版同步器 · CLI 入口
默认 --dry-run: 只扫描、比对、呈现，不写任何 spoke 文件。
--apply: 逐文件确认后备份并写入。
"""
import argparse
import os
import sys

from app.constants import DiffState, MANAGED_FILE_MAP
from app.scanner import scan, SpokeFilePair
from app.splitter import split_file, SplitStatus
from app.differ import diff_general
from app.reporter import build_report, print_terminal, write_markdown, ReportItem
from app.applier import apply_file


def main():
    parser = argparse.ArgumentParser(
        description="母版同步器 — 把 hub 通用规则更新辅助下发到各 spoke",
    )
    parser.add_argument(
        "--hub",
        default=None,
        help="hub 目录路径(默认: 脚本所在目录的上两级即为 设计工具/)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="执行写入(默认 dry-run,只呈现不写)",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过逐文件确认(仅 --apply 时生效)",
    )
    lesson_group = parser.add_mutually_exclusive_group()
    lesson_group.add_argument(
        "--lesson-up", action="store_true",
        help="上行模式：收集 [↑] 提案写入 hub")
    lesson_group.add_argument(
        "--lesson-down", action="store_true",
        help="下行模式：hub 新增教训下发到各 spoke")
    args = parser.parse_args()

    dry_run = not args.apply

    if args.hub:
        hub_dir = os.path.abspath(args.hub)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        design_root = os.path.dirname(os.path.dirname(script_dir))
        hub_dir = os.path.join(design_root, "设计工具")

    if not os.path.isdir(hub_dir):
        print(f"错误: hub 目录不存在: {hub_dir}", file=sys.stderr)
        sys.exit(1)

    mode_label = "DRY-RUN (只呈现不写)" if dry_run else "APPLY 模式(将写入 spoke 文件)"
    print(f"母版同步器 · {mode_label}")
    print(f"hub: {hub_dir}")
    print()

    if args.lesson_up:
        run_lesson_up(hub_dir, dry_run=dry_run, confirm=not args.yes)
    elif args.lesson_down:
        run_lesson_down(hub_dir, dry_run=dry_run, confirm=not args.yes)
    else:
        run(hub_dir, dry_run=dry_run, confirm=not args.yes)

def run(hub_dir: str, dry_run: bool = True, confirm: bool = True) -> int:
    """核心流水线: 扫描→切分→比对→呈现→[应用]。返回 0 正常。"""
    # 1. 扫描
    pairs = scan(hub_dir)
    if not pairs:
        print("无受管项目。")
        return 0

    # 2. 分区切分 + 比对
    results: list[tuple[SpokeFilePair, object | None]] = []
    outdated_items: list[tuple[SpokeFilePair, list[str], list[str]]] = []

    for pair in pairs:
        if pair.state == DiffState.MISSING_FILE:
            results.append((pair, None))
            continue

        cfg = _cfg_for_file(pair.file_name)

        # 读 hub 母版
        try:
            with open(pair.hub_path, encoding="utf-8") as f:
                hub_lines = f.readlines()
        except OSError as e:
            pair.state = DiffState.MISSING_FILE
            pair.error_reason = f"无法读取 hub 母版: {e}"
            results.append((pair, None))
            continue

        # 读 spoke 副本
        try:
            with open(pair.spoke_path, encoding="utf-8") as f:
                spoke_lines = f.readlines()
        except OSError as e:
            pair.state = DiffState.MISSING_FILE
            pair.error_reason = f"无法读取 spoke 文件: {e}"
            results.append((pair, None))
            continue

        # 切分
        hub_split = split_file(hub_lines, cfg)
        spoke_split = split_file(spoke_lines, cfg)

        if hub_split.status == SplitStatus.STRUCTURE_ERROR:
            pair.state = DiffState.STRUCTURE_ERROR
            pair.error_reason = "hub 母版结构异常(锚点缺失/重复)"
            results.append((pair, None))
            continue

        if spoke_split.status == SplitStatus.STRUCTURE_ERROR:
            pair.state = DiffState.STRUCTURE_ERROR
            pair.error_reason = "spoke 文件结构异常(锚点缺失/重复)"
            results.append((pair, None))
            continue

        # 比对
        diff_result = diff_general(hub_split, spoke_split)
        pair.state = diff_result.state
        results.append((pair, diff_result))

        if diff_result.state == DiffState.OUTDATED:
            outdated_items.append((pair, hub_split.general, spoke_split.private))

    # 3. 呈现
    report = build_report(results)
    print_terminal(report)

    # 写 Markdown 报告
    report_path = write_markdown(report, hub_dir)
    print(f"\nMarkdown 报告: {report_path}")

    # 4. 应用(仅 --apply)
    if dry_run:
        print("\n[Dry-run 完成，未修改任何 spoke 文件。加 --apply 以执行写入。]")
        return 0

    if not outdated_items:
        print("\n无待同步项。")
        return 0

    # 逐文件确认
    applied = []
    for pair, hub_general, spoke_private in outdated_items:
        if confirm:
            print(f"\n待同步: {pair.spoke_name}/{pair.file_name}")
            answer = input("  拉取此更新? [y/N] ").strip().lower()
            if answer != "y":
                print("  跳过。")
                continue

        result = apply_file(
            hub_dir=hub_dir,
            spoke_path=pair.spoke_path,
            file_name=pair.file_name,
            hub_general=hub_general,
            spoke_private=spoke_private,
            dry_run=False,
        )

        if result.success:
            applied.append(ReportItem(
                spoke_name=pair.spoke_name,
                file_name=pair.file_name,
                state=DiffState.OUTDATED,
                backup_path=result.backup_path,
            ))
            print(f"  ✅ 已写入,备份: {result.backup_path}")
        else:
            print(f"  ❌ 失败: {result.error}")

    # 追加 applied 记录并重写报告
    if applied:
        report.applied = applied
        write_markdown(report, hub_dir)
        print(f"\n已更新报告: {report_path}")

    return 0


def run_lesson_up(hub_dir: str, dry_run: bool = True, confirm: bool = True) -> int:
    """上行流水线：收集 [↑] → 比对 → 呈现 → [应用]。"""
    from app.lesson_parser import parse_lessons, Lesson
    from app.lesson_differ import up_diff, UpCandidate, UpState
    from app.lesson_reporter import print_terminal_up, write_markdown_up

    pairs = scan(hub_dir)
    hub_path = os.path.join(hub_dir, "审查清单.md")

    if not os.path.isfile(hub_path):
        print("错误: hub 无 审查清单.md", file=sys.stderr)
        return 1

    with open(hub_path, encoding="utf-8") as f:
        hub_all = f.readlines()
    cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
    hub_split = split_file(hub_all, cfg)
    hub_lessons = parse_lessons(hub_split.private)

    candidates: list[UpCandidate] = []
    for pair in pairs:
        if pair.file_name != "审查清单.md":
            continue
        if not os.path.isfile(pair.spoke_path):
            continue
        with open(pair.spoke_path, encoding="utf-8") as f:
            spoke_all = f.readlines()
        spoke_split = split_file(spoke_all, cfg)
        spoke_lessons = parse_lessons(spoke_split.private)
        for lesson in spoke_lessons:
            if lesson.has_up_marker:
                candidates.append(UpCandidate(pair.spoke_name, lesson))

    if not candidates:
        print("无上行候选。")
        return 0

    results = up_diff(hub_lessons, candidates)
    print_terminal_up(results)
    report_path = write_markdown_up(results, hub_dir)
    print(f"\nMarkdown 报告: {report_path}")

    if dry_run:
        print("\n[Dry-run 完成，未修改任何文件。加 --apply 以执行写入。]")
        return 0

    # apply
    from app.lesson_applier import write_hub, ApplyResult
    applied = []
    for r in results:
        if r.state == UpState.CONFLICT:
            continue
        if r.state == UpState.ALREADY_SYNCED:
            print(f"\nL{r.lesson.l_number} ({r.spoke_name}): 已同步，可移除 [↑]")
            continue

        action = "更新" if r.state == UpState.UPDATE else "新增"
        mode = "replace" if r.state == UpState.UPDATE else "insert"

        if confirm:
            print(f"\n待{action}: L{r.lesson.l_number} ({r.spoke_name})")
            answer = input(f"  确认{action}? [y/N] ").strip().lower()
            if answer != "y":
                print("  跳过。")
                continue

        # 剥除 [↑] 标记（调用方职责），写回干净的 Lesson
        cleaned_lines = [line.replace(" [↑]", "") for line in r.lesson.raw_lines]
        clean_lesson = Lesson(
            l_number=r.lesson.l_number,
            raw_lines=cleaned_lines,
            has_up_marker=False,
        )
        result = write_hub(hub_path, clean_lesson, mode, dry_run=False)
        if result.success:
            print(f"  ✅ 已{action},备份: {result.backup_path}")
            applied.append(r)
        else:
            print(f"  ❌ 失败: {result.error}")

    if applied:
        write_markdown_up(results, hub_dir, applied=applied)
        print(f"\n已更新报告: {report_path}")
    return 0


def run_lesson_down(hub_dir: str, dry_run: bool = True, confirm: bool = True) -> int:
    """下行流水线：解析 hub → 比对每 spoke → 呈现 → [应用]。"""
    from app.lesson_parser import parse_lessons
    from app.lesson_differ import down_diff, DownState
    from app.lesson_reporter import print_terminal_down, write_markdown_down

    hub_path = os.path.join(hub_dir, "审查清单.md")
    if not os.path.isfile(hub_path):
        print("错误: hub 无 审查清单.md", file=sys.stderr)
        return 1

    with open(hub_path, encoding="utf-8") as f:
        hub_all = f.readlines()
    cfg = {"general_scope": "before_anchor", "boundary_anchor": "# 第二部分"}
    hub_split = split_file(hub_all, cfg)
    hub_lessons = parse_lessons(hub_split.private)

    pairs = scan(hub_dir)
    by_spoke: dict[str, list] = {}
    spoke_paths: dict[str, str] = {}
    for pair in pairs:
        if pair.file_name != "审查清单.md":
            continue
        if not os.path.isfile(pair.spoke_path):
            continue
        with open(pair.spoke_path, encoding="utf-8") as f:
            spoke_all = f.readlines()
        spoke_split = split_file(spoke_all, cfg)
        spoke_lessons = parse_lessons(spoke_split.private)
        by_spoke[pair.spoke_name] = down_diff(hub_lessons, spoke_lessons)
        spoke_paths[pair.spoke_name] = pair.spoke_path

    if not by_spoke:
        print("无受管 spoke。")
        return 0

    print_terminal_down(by_spoke)
    report_path = write_markdown_down(by_spoke, hub_dir)
    print(f"\nMarkdown 报告: {report_path}")

    if dry_run:
        print("\n[Dry-run 完成，未修改任何 spoke。加 --apply 以执行写入。]")
        return 0

    # apply
    from app.lesson_applier import write_spoke
    applied = []
    for spoke_name, items in sorted(by_spoke.items()):
        new_items = [r for r in items if r.state == DownState.NEW_IN_HUB]
        if not new_items:
            continue
        for r in new_items:
            if confirm:
                print(f"\n待写入: L{r.lesson.l_number} → {spoke_name}")
                answer = input(f"  确认? [y/N] ").strip().lower()
                if answer != "y":
                    print("  跳过。")
                    continue
            result = write_spoke(spoke_paths[spoke_name], r.lesson, dry_run=False)
            if result.success:
                print(f"  ✅ 已写入,备份: {result.backup_path}")
                applied.append(r)
            else:
                print(f"  ❌ 失败: {result.error}")

    if applied:
        write_markdown_down(by_spoke, hub_dir, applied=applied)
        print(f"\n已更新报告: {report_path}")
    return 0



def _cfg_for_file(file_name: str) -> dict:
    mf = MANAGED_FILE_MAP.get(file_name)
    if mf is None:
        return {"general_scope": "whole_file", "boundary_anchor": None}
    return {
        "general_scope": mf.general_scope,
        "boundary_anchor": mf.boundary_anchor,
    }


if __name__ == "__main__":
    main()
