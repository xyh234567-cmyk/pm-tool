"""总览/详情/KPI 组装, 口径见 03-3 §C。"""
from __future__ import annotations
from datetime import date
from typing import Any

from app.common.enums import TASK_STATUS_COLOR, DONE_STATUSES
from app.analytics.delay import (
    is_project_delayed, is_task_delayed, days_to_deliver, deliver_state,
    get_delayed_projects, get_delayed_tasks,
)
from app.analytics.resource import count_conflict_persons, get_resource_conflicts


def build_task_bar_info(t: dict[str, Any]) -> dict[str, Any]:
    """给任务行补充甘特颜色语义。"""
    status = (t.get("status") or "").strip()
    progress = t.get("progress_pct")

    color = "todo"  # 默认灰
    if status in DONE_STATUSES or progress == 100.0:
        color = "done"
    elif status in TASK_STATUS_COLOR.get("doing", set()):
        color = "doing"
    elif progress and 0 < progress < 100:
        color = "doing"

    return {**t, "bar_color": color}


def get_overview(
    projects: list[dict],
    tasks_by_project: dict[str, list[dict]],
    members: list[dict],
    today: date,
    soon_days: int,
) -> dict[str, Any]:
    """总览: KPI + 项目行。"""
    delayed_projects = get_delayed_projects(projects, tasks_by_project, today)
    conflict_count = count_conflict_persons(members, today)

    # 在管项目数
    total = len(projects)

    # 临近交付项目数
    soon_count = 0
    for p in projects:
        d = days_to_deliver(p.get("plan_deliver_date"), today)
        state = deliver_state(d, soon_days)
        if state == "soon":
            soon_count += 1

    # 项目行
    rows = []
    for p in projects:
        pdd = p.get("plan_deliver_date")
        d = days_to_deliver(pdd, today)
        state = deliver_state(d, soon_days)
        tasks = tasks_by_project.get(p["biz_id"], [])
        delayed = is_project_delayed(p, tasks, today)
        rows.append({
            "biz_id": p["biz_id"],
            "project_name": p.get("project_name", ""),
            "owner_name": p.get("owner_name", ""),
            "stage_status": p.get("stage_status", ""),
            "progress_pct": p.get("progress_pct"),
            "risk_level": p.get("risk_level", ""),
            "plan_deliver_date": pdd,
            "days_to_deliver": d,
            "deliver_state": state,
            "delay_flag": delayed,
        })

    return {
        "kpi": {
            "total": total,
            "delayed": len(delayed_projects),
            "conflict_persons": conflict_count,
            "soon_deliver": soon_count,
        },
        "rows": rows,
    }


def build_project_detail(
    proj: dict[str, Any],
    members: list[dict],
    tasks: list[dict],
    today: date,
) -> dict[str, Any]:
    """项目详情: 主表全字段 + members + tasks(含颜色+延期标记)。"""
    enriched_tasks = [build_task_bar_info(t) for t in tasks]

    delayed_flag = is_project_delayed(proj, tasks, today)
    # 甘特时间域
    all_starts = []
    all_ends = []
    for t in enriched_tasks:
        for k in ("plan_start", "actual_start"):
            if t.get(k):
                try:
                    all_starts.append(date.fromisoformat(t[k]))
                except (ValueError, TypeError):
                    pass
        if t.get("plan_end"):
            try:
                all_ends.append(date.fromisoformat(t["plan_end"]))
            except (ValueError, TypeError):
                pass
    domain_start = min(all_starts).strftime("%Y-%m-%d") if all_starts else today.strftime("%Y-%m-%d")
    domain_end = max(all_ends).strftime("%Y-%m-%d") if all_ends else today.strftime("%Y-%m-%d")

    return {
        **proj,
        "members": members,
        "tasks": enriched_tasks,
        "delayed": delayed_flag,
        "gantt_domain": {"start": domain_start, "end": domain_end, "today": today.strftime("%Y-%m-%d")},
    }
