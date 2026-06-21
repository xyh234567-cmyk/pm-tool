"""延期判定: 任务级与项目级, 口径见 03-3 §A。"""
from __future__ import annotations
from datetime import date
from typing import Any

from app.common.enums import DONE_STATUSES


def is_task_delayed(t: dict[str, Any], today: date) -> bool:
    """任务延期: plan_end 非空 且 < today 且未完成。"""
    pe = t.get("plan_end")
    if not pe:
        return False
    status = (t.get("status") or "").strip()
    progress = t.get("progress_pct")
    done = status in DONE_STATUSES or progress == 100.0
    return (pe < today.strftime("%Y-%m-%d")) and not done


def is_project_delayed(p: dict[str, Any], tasks: list[dict], today: date) -> bool:
    """项目延期: 任一任务延期 OR plan_deliver 过期且未交付。"""
    if any(is_task_delayed(t, today) for t in tasks):
        return True
    pdd = p.get("plan_deliver_date")
    add = p.get("actual_deliver_date")
    if pdd and pdd < today.strftime("%Y-%m-%d") and not add:
        return True
    return False


def get_delayed_tasks(
    projects: list[dict], tasks_by_project: dict[str, list[dict]], today: date
) -> list[dict]:
    """所有延期任务列表。"""
    result = []
    for p in projects:
        for t in tasks_by_project.get(p["biz_id"], []):
            if is_task_delayed(t, today):
                days = (today - date.fromisoformat(t["plan_end"])).days
                result.append({
                    "biz_id": p["biz_id"],
                    "project_name": p.get("project_name", ""),
                    "task_name": t.get("task_name", ""),
                    "owner": t.get("owner", ""),
                    "plan_end": t["plan_end"],
                    "overdue_days": days,
                })
    return result


def get_delayed_projects(
    projects: list[dict], tasks_by_project: dict[str, list[dict]], today: date
) -> list[dict]:
    """延期项目列表。"""
    result = []
    for p in projects:
        tasks = tasks_by_project.get(p["biz_id"], [])
        if is_project_delayed(p, tasks, today):
            reasons = []
            if any(is_task_delayed(t, today) for t in tasks):
                reasons.append("任务延期")
            pdd = p.get("plan_deliver_date")
            add = p.get("actual_deliver_date")
            if pdd and pdd < today.strftime("%Y-%m-%d") and not add:
                reasons.append("到期未交付")
            pdd_val = pdd or ""
            days = (today - date.fromisoformat(pdd_val)).days if pdd else 0
            result.append({
                "biz_id": p["biz_id"],
                "project_name": p.get("project_name", ""),
                "owner_name": p.get("owner_name", ""),
                "plan_deliver_date": pdd,
                "overdue_days": days,
                "reasons": "/".join(reasons),
            })
    return result


def days_to_deliver(pdd: str | None, today: date) -> int | None:
    """距交付天数: 正数=剩余, 负数=逾期。"""
    if not pdd:
        return None
    return (date.fromisoformat(pdd) - today).days


def deliver_state(days: int | None, soon_days: int) -> str:
    """交付状态: overdue / soon / normal。"""
    if days is None:
        return "normal"
    if days < 0:
        return "overdue"
    if days <= soon_days:
        return "soon"
    return "normal"
