"""analytics 模块单元测试: 延期、撞车、KPI 组装。口径见 03-3。"""
from __future__ import annotations
from datetime import date
import pytest

from app.analytics.delay import (
    is_task_delayed, is_project_delayed,
    get_delayed_tasks, get_delayed_projects,
    days_to_deliver, deliver_state,
)
from app.analytics.resource import get_resource_conflicts, count_conflict_persons
from app.analytics.dashboard import get_overview, build_task_bar_info


@pytest.fixture
def today():
    return date(2026, 6, 21)


# ── 延期判定 ────────────────────────────────────────────

def test_task_delayed(today):
    """plan_end 已过 + 未完成 → 延期。"""
    assert is_task_delayed({
        "plan_end": "2026-06-15", "status": "进行中", "progress_pct": 50
    }, today)

def test_task_completed_not_delayed(today):
    """状态已完成 → 即使过期也不算延期。"""
    assert not is_task_delayed({
        "plan_end": "2026-06-10", "status": "已完成", "progress_pct": 100
    }, today)

def test_task_no_plan_end(today):
    """无 plan_end → 不延期。"""
    assert not is_task_delayed({"status": "进行中"}, today)

def test_project_delayed_by_task(today):
    """有延期任务 → 项目延期。"""
    assert is_project_delayed(
        {"plan_deliver_date": None},
        [{"plan_end": "2026-06-15", "status": "未开始"}],
        today,
    )

def test_project_delayed_by_deadline(today):
    """到期未交付 → 项目延期。"""
    assert is_project_delayed(
        {"plan_deliver_date": "2026-06-15", "actual_deliver_date": None},
        [],
        today,
    )

def test_days_to_deliver(today):
    assert days_to_deliver("2026-06-30", today) == 9
    assert days_to_deliver("2026-06-20", today) == -1
    assert days_to_deliver(None, today) is None

def test_deliver_state(today):
    assert deliver_state(days_to_deliver("2026-06-15", today), 7) == "overdue"
    assert deliver_state(days_to_deliver("2026-06-25", today), 7) == "soon"
    assert deliver_state(days_to_deliver("2026-07-15", today), 7) == "normal"


# ── 资源撞车 ────────────────────────────────────────────

def test_conflict_basic(today):
    """陈庆阳 30%+80% 在重叠期内 → 撞车, peak=110。"""
    members = [
        {"name": "陈庆阳", "join_start": "2026-04-20", "join_end": "2026-06-30",
         "workload_pct": 30.0, "biz_id": "RW2026-001", "project_name": "隔离网关"},
        {"name": "陈庆阳", "join_start": "2026-05-01", "join_end": "2026-06-30",
         "workload_pct": 80.0, "biz_id": "RW2026-002", "project_name": "其他项目"},
    ]
    conflicts = get_resource_conflicts(members, today)
    assert len(conflicts) == 1
    assert conflicts[0]["name"] == "陈庆阳"
    assert conflicts[0]["peak_total"] == 110.0
    assert conflicts[0]["includes_today"]

def test_no_conflict_single_project(today):
    """单项目不构成撞车。"""
    members = [
        {"name": "陈庆阳", "join_start": "2026-04-20", "join_end": "2026-06-30",
         "workload_pct": 110.0, "biz_id": "RW2026-001", "project_name": "隔离网关"},
    ]
    assert len(get_resource_conflicts(members, today)) == 0

def test_no_conflict_no_overlap(today):
    """时间不重叠 → 不撞车。"""
    members = [
        {"name": "张三", "join_start": "2026-01-01", "join_end": "2026-02-28",
         "workload_pct": 100.0, "biz_id": "A", "project_name": "P1"},
        {"name": "张三", "join_start": "2026-03-01", "join_end": "2026-04-30",
         "workload_pct": 100.0, "biz_id": "B", "project_name": "P2"},
    ]
    assert len(get_resource_conflicts(members, today)) == 0

def test_conflict_past_not_includes_today(today):
    """冲突段在 today 之前 → includes_today=False。"""
    members = [
        {"name": "张三", "join_start": "2026-01-01", "join_end": "2026-02-28",
         "workload_pct": 80.0, "biz_id": "A", "project_name": "P1"},
        {"name": "张三", "join_start": "2026-02-01", "join_end": "2026-03-15",
         "workload_pct": 80.0, "biz_id": "B", "project_name": "P2"},
    ]
    conflicts = get_resource_conflicts(members, today)
    if conflicts:
        assert not conflicts[0]["includes_today"]


# ── 总览组装 ────────────────────────────────────────────

def test_overview_basic(today):
    projects = [
        {"biz_id": "RW2026-001", "project_name": "隔离网关",
         "owner_name": "刘长城", "plan_deliver_date": "2026-06-25",
         "progress_pct": 65.0, "risk_level": "中风险", "stage_status": "开发中"},
    ]
    tasks = {"RW2026-001": [
        {"plan_end": "2026-06-30", "status": "进行中", "progress_pct": 50},
    ]}
    members = [
        {"name": "陈庆阳", "join_start": "2026-04-20", "join_end": "2026-06-30",
         "workload_pct": 30.0, "biz_id": "RW2026-001", "project_name": "隔离网关"},
    ]
    ov = get_overview(projects, tasks, members, today, 7)
    assert ov["kpi"]["total"] == 1
    assert ov["kpi"]["delayed"] == 0
    assert ov["kpi"]["soon_deliver"] == 1
    assert len(ov["rows"]) == 1

def test_overview_with_delay(today):
    projects = [
        {"biz_id": "RW2026-001", "project_name": "隔离网关",
         "owner_name": "刘长城", "plan_deliver_date": "2026-06-15",
         "progress_pct": 65.0, "risk_level": "中风险"},
    ]
    tasks = {"RW2026-001": [
        {"plan_end": "2026-06-15", "status": "未开始"},
    ]}
    members = []
    ov = get_overview(projects, tasks, members, today, 7)
    assert ov["kpi"]["delayed"] == 1
    assert ov["rows"][0]["delay_flag"] is True
    assert ov["rows"][0]["deliver_state"] == "overdue"


# ── 任务颜色 ────────────────────────────────────────────

def test_task_bar_color():
    assert build_task_bar_info({"status": "已完成"})["bar_color"] == "done"
    assert build_task_bar_info({"status": "进行中"})["bar_color"] == "doing"
    assert build_task_bar_info({"status": "未开始"})["bar_color"] == "todo"
    assert build_task_bar_info({"status": "", "progress_pct": 50})["bar_color"] == "doing"
