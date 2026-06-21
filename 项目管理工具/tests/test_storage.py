"""storage 模块单元测试: 建表、幂等 upsert、查询、空库。

每个测试使用独立的临时 DB 文件, 测完清理。
"""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

import pytest

from app.common.models import Project, Member, Task, QcIssue
from app.storage.db import init_db, get_db
from app.storage.repository import (
    upsert_snapshot,
    start_scan_run,
    finalize_scan_run,
    insert_qc,
    get_latest_projects,
    get_project_detail,
    get_latest_members_all,
    get_qc_issues,
    get_last_scan_run,
    list_snapshot_dates,
)


@pytest.fixture
def db_path():
    """每个测试用临时 SQLite 文件, 自动清理。"""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_pm_")
    os.close(fd)
    yield path
    try:
        Path(path).unlink()
        Path(path + "-wal").unlink(missing_ok=True)
        Path(path + "-shm").unlink(missing_ok=True)
    except OSError:
        pass


def _make_project(
    biz_id="RW2026-001",
    snap_date="2026-06-17",
    **kwargs,
) -> Project:
    """快捷构造一个带 members/tasks 的 Project。

    kwargs 可覆盖任意 Project 字段(如 project_name)。
    """
    defaults = {"project_name": "测试项目"}
    defaults.update(kwargs)
    p = Project(biz_id=biz_id, snap_date=snap_date, **defaults)
    p.members = [
        Member(row_idx=2, name="张三", role="开发", workload_pct=50.0, is_external=False),
        Member(row_idx=3, name="外协", role="测试", workload_pct=30.0, is_external=True),
    ]
    p.tasks = [
        Task(row_idx=5, seq="1", task_name="需求分析", status="已完成",
             plan_start="2026-01-01", plan_end="2026-03-01"),
        Task(row_idx=6, seq="2", task_name="开发", status="进行中",
             plan_start="2026-03-02", plan_end="2026-06-15"),
    ]
    return p


# ── 建表 ────────────────────────────────────────────────

def test_init_db_creates_tables(db_path):
    """init_db 后 5 张表和 3 个索引均应存在。"""
    init_db(db_path)
    conn = get_db(db_path)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        assert table_names >= {
            "snapshot", "snapshot_member", "snapshot_task",
            "qc_issue", "scan_run",
        }

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        index_names = {r["name"] for r in indexes}
        assert index_names >= {
            "idx_snapshot_latest", "idx_member_person", "idx_task_proj",
        }
    finally:
        conn.close()


def test_init_db_idempotent(db_path):
    """两次 init_db 不报错。"""
    init_db(db_path)
    init_db(db_path)  # 不应抛异常


# ── upsert_snapshot ─────────────────────────────────────

def test_upsert_insert_new(db_path):
    """首次写入返回 'inserted', 数据完整入库。"""
    p = _make_project()
    result = upsert_snapshot(p, db_path)
    assert result == "inserted"

    # 验证主表
    conn = get_db(db_path)
    try:
        snap = conn.execute(
            "SELECT * FROM snapshot WHERE biz_id=? AND snap_date=?",
            ("RW2026-001", "2026-06-17"),
        ).fetchone()
        assert snap is not None
        assert snap["project_name"] == "测试项目"
        assert snap["biz_type"] is None
        assert snap["ingested_at"] is not None  # 自动生成

        members = conn.execute(
            "SELECT * FROM snapshot_member WHERE biz_id=? AND snap_date=? ORDER BY row_idx",
            ("RW2026-001", "2026-06-17"),
        ).fetchall()
        assert len(members) == 2
        assert members[0]["name"] == "张三"
        assert members[0]["biz_id"] == "RW2026-001"     # 从父注入
        assert members[1]["is_external"] == 1

        tasks = conn.execute(
            "SELECT * FROM snapshot_task WHERE biz_id=? AND snap_date=? ORDER BY row_idx",
            ("RW2026-001", "2026-06-17"),
        ).fetchall()
        assert len(tasks) == 2
        assert tasks[0]["biz_id"] == "RW2026-001"       # 从父注入
    finally:
        conn.close()


def test_upsert_update_existing(db_path):
    """同键写第二次返回 'updated', 数据覆盖, 子表行数正确。"""
    p1 = _make_project()
    upsert_snapshot(p1, db_path)

    # 修改 project_name, 仅保留 1 个 member
    p2 = _make_project(project_name="更新项目")
    p2.members = [Member(row_idx=2, name="李四", role="开发", workload_pct=80.0)]
    p2.tasks = [Task(row_idx=5, seq="1", task_name="新任务", status="未开始")]
    result = upsert_snapshot(p2, db_path)
    assert result == "updated"

    conn = get_db(db_path)
    try:
        snap = conn.execute(
            "SELECT * FROM snapshot WHERE biz_id=? AND snap_date=?",
            ("RW2026-001", "2026-06-17"),
        ).fetchone()
        assert snap["project_name"] == "更新项目"

        members = conn.execute(
            "SELECT * FROM snapshot_member WHERE biz_id=? AND snap_date=?",
            ("RW2026-001", "2026-06-17"),
        ).fetchall()
        assert len(members) == 1
        assert members[0]["name"] == "李四"

        tasks = conn.execute(
            "SELECT * FROM snapshot_task WHERE biz_id=? AND snap_date=?",
            ("RW2026-001", "2026-06-17"),
        ).fetchall()
        assert len(tasks) == 1
    finally:
        conn.close()


def test_upsert_does_not_cross_contaminate(db_path):
    """同一 biz_id 不同 snap_date 互不干扰。"""
    p_jun = _make_project(snap_date="2026-06-17")
    p_jul = _make_project(snap_date="2026-07-20", project_name="七月快照")
    upsert_snapshot(p_jun, db_path)
    upsert_snapshot(p_jul, db_path)

    conn = get_db(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM snapshot WHERE biz_id=?",
            ("RW2026-001",)
        ).fetchone()["c"]
        assert count == 2

        # 各自 members 独立
        m_jun = conn.execute(
            "SELECT COUNT(*) AS c FROM snapshot_member WHERE biz_id=? AND snap_date=?",
            ("RW2026-001", "2026-06-17"),
        ).fetchone()["c"]
        m_jul = conn.execute(
            "SELECT COUNT(*) AS c FROM snapshot_member WHERE biz_id=? AND snap_date=?",
            ("RW2026-001", "2026-07-20"),
        ).fetchone()["c"]
        assert m_jun == 2
        assert m_jul == 2
    finally:
        conn.close()


# ── get_latest_projects ────────────────────────────────

def test_get_latest_projects_returns_newest(db_path):
    """多快照时只返回每个 biz_id 的最新一条。"""
    p_old = _make_project(snap_date="2026-06-10", project_name="旧快照")
    p_new = _make_project(snap_date="2026-06-20", project_name="新快照")
    upsert_snapshot(p_old, db_path)
    upsert_snapshot(p_new, db_path)

    latest = get_latest_projects(db_path)
    assert len(latest) == 1
    assert latest[0]["project_name"] == "新快照"
    assert latest[0]["snap_date"] == "2026-06-20"


def test_get_latest_multi_project(db_path):
    """两个不同 biz_id 各取最新。"""
    p_a = _make_project(biz_id="RW2026-001", snap_date="2026-06-17")
    p_b = _make_project(biz_id="RW2026-002", snap_date="2026-06-18",
                         project_name="项目B")
    upsert_snapshot(p_a, db_path)
    upsert_snapshot(p_b, db_path)

    latest = get_latest_projects(db_path)
    assert len(latest) == 2
    names = {r["biz_id"] for r in latest}
    assert names == {"RW2026-001", "RW2026-002"}


# ── empty DB ────────────────────────────────────────────

def test_empty_db_queries_return_empty(db_path):
    """空库所有查询返回空列表 / None。"""
    assert get_latest_projects(db_path) == []
    assert get_project_detail("RW2026-001", db_path) is None
    assert get_latest_members_all(db_path) == []
    assert get_qc_issues(db_path) == []
    assert get_last_scan_run(db_path) is None
    assert list_snapshot_dates("RW2026-001", db_path) == []


# ── scan_run / qc ──────────────────────────────────────

def test_start_and_finalize_scan_run(db_path):
    """start_scan_run 返回 run_id; finalize 回填统计。"""
    run_id = start_scan_run(db_path, started_at="2026-06-20T10:00:00Z")
    assert isinstance(run_id, int)
    assert run_id > 0

    finalize_scan_run(run_id, {
        "finished_at": "2026-06-20T10:01:00Z",
        "files_total": 3, "inserted": 2, "updated": 1,
        "skipped": 0, "qc_errors": 0, "qc_warnings": 5,
    }, db_path)

    run = get_last_scan_run(db_path)
    assert run is not None
    assert run["run_id"] == run_id
    assert run["finished_at"] == "2026-06-20T10:01:00Z"
    assert run["inserted"] == 2
    assert run["qc_warnings"] == 5


def test_insert_qc_and_query(db_path):
    """写入 QC 问题(带 run_id), 查询能取回。"""
    run_id = start_scan_run(db_path, started_at="2026-06-20T10:00:00Z")
    finalize_scan_run(run_id, {
        "finished_at": "2026-06-20T10:01:00Z",
        "files_total": 1, "inserted": 1,
        "updated": 0, "skipped": 0, "qc_errors": 0, "qc_warnings": 1,
    }, db_path)

    issues = [
        QcIssue(biz_id="RW2026-001", snap_date="2026-06-17",
                source_filename="test.xlsx", severity="warning",
                issue_type="MEMBER_EXTERNAL", location="人员区行3",
                message="人员姓名为外协"),
    ]
    insert_qc(issues, run_id, db_path)

    rows = get_qc_issues(db_path, latest_run_only=False)
    assert len(rows) == 1
    assert rows[0]["issue_type"] == "MEMBER_EXTERNAL"
    assert rows[0]["run_id"] == run_id


def test_qc_latest_run_only_isolation(db_path):
    """两次扫描批次, latest_run_only=True 只返回第二次的质检问题。"""
    # 第一批次
    run1 = start_scan_run(db_path, started_at="2026-06-19T10:00:00Z")
    insert_qc([
        QcIssue(biz_id="RW2026-001", snap_date="2026-06-19",
                source_filename="a.xlsx", severity="warning",
                issue_type="BAD_DATE", location="日期列",
                message="日期无法解析"),
        QcIssue(biz_id="RW2026-002", snap_date="2026-06-19",
                source_filename="b.xlsx", severity="error",
                issue_type="BIZ_ID_MISSING", location="业务ID",
                message="业务ID为空"),
    ], run1, db_path)
    finalize_scan_run(run1, {
        "finished_at": "2026-06-19T10:01:00Z",
        "files_total": 2, "inserted": 2, "updated": 0,
        "skipped": 0, "qc_errors": 1, "qc_warnings": 1,
    }, db_path)

    # 第二批次(最新)
    run2 = start_scan_run(db_path, started_at="2026-06-20T10:00:00Z")
    insert_qc([
        QcIssue(biz_id="RW2026-001", snap_date="2026-06-20",
                source_filename="c.xlsx", severity="warning",
                issue_type="REQUIRED_EMPTY", location="项目名称",
                message="项目名称为空"),
    ], run2, db_path)
    finalize_scan_run(run2, {
        "finished_at": "2026-06-20T10:01:00Z",
        "files_total": 1, "inserted": 1, "updated": 0,
        "skipped": 0, "qc_errors": 0, "qc_warnings": 1,
    }, db_path)

    # latest_run_only=True → 只返回第二批次(REQUIRED_EMPTY)
    latest = get_qc_issues(db_path, latest_run_only=True)
    assert len(latest) == 1
    assert latest[0]["issue_type"] == "REQUIRED_EMPTY"
    assert latest[0]["run_id"] == run2

    # latest_run_only=False → 返回全部 3 条
    all_issues = get_qc_issues(db_path, latest_run_only=False)
    assert len(all_issues) == 3
    issue_types = {r["issue_type"] for r in all_issues}
    assert issue_types == {"BAD_DATE", "BIZ_ID_MISSING", "REQUIRED_EMPTY"}


# ── member / detail ─────────────────────────────────────

def test_get_latest_members_excludes_external(db_path):
    """get_latest_members_all 不含 is_external=1 的行。"""
    p = _make_project()
    upsert_snapshot(p, db_path)
    members = get_latest_members_all(db_path)
    assert len(members) == 1
    assert members[0]["name"] == "张三"


def test_get_project_detail_with_members(db_path):
    """get_project_detail 返回主表 + members + tasks。"""
    p = _make_project()
    upsert_snapshot(p, db_path)
    detail = get_project_detail("RW2026-001", db_path)
    assert detail is not None
    assert detail["biz_id"] == "RW2026-001"
    assert len(detail["members"]) == 2
    assert len(detail["tasks"]) == 2
    assert detail["members"][0]["name"] == "张三"
    assert detail["tasks"][0]["task_name"] == "需求分析"


def test_get_project_detail_respects_latest(db_path):
    """get_project_detail 取最新快照, 不是旧快照。"""
    p_old = _make_project(snap_date="2026-06-10", project_name="旧")
    p_new = _make_project(snap_date="2026-06-20", project_name="新")
    upsert_snapshot(p_old, db_path)
    upsert_snapshot(p_new, db_path)
    detail = get_project_detail("RW2026-001", db_path)
    assert detail["project_name"] == "新"


def test_list_snapshot_dates(db_path):
    """list_snapshot_dates 返回某 biz_id 所有快照日期。"""
    upsert_snapshot(_make_project(snap_date="2026-06-10"), db_path)
    upsert_snapshot(_make_project(snap_date="2026-06-20"), db_path)
    dates = list_snapshot_dates("RW2026-001", db_path)
    assert dates == ["2026-06-10", "2026-06-20"]
