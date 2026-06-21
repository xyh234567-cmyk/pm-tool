"""存储层读写接口: 快照幂等写入、质检/批次写入、查询。

约定: 日期 YYYY-MM-DD 文本存; 金额/百分比 REAL; 空值 NULL。
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from app.common.models import Project, Member, Task, QcIssue
from app.storage.db import get_db


def _now_iso() -> str:
    """当前 UTC 时间字符串, 用于 ingested_at / detected_at。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 快照写入 ─────────────────────────────────────────────

def upsert_snapshot(p: Project, db_path: str) -> str:
    """幂等写入一个项目快照(主表 + 子表), 单事务。

    唯一键: (biz_id, snap_date)。已存在则覆盖(子表先删后插)。
    返回 'inserted' | 'updated'。
    """
    conn = get_db(db_path)
    try:
        cur = conn.execute(
            "SELECT 1 FROM snapshot WHERE biz_id=? AND snap_date=?",
            (p.biz_id, p.snap_date),
        )
        existed = cur.fetchone() is not None

        # 主表 upsert
        conn.execute(
            """INSERT INTO snapshot (
                biz_id, snap_date, project_name, biz_type, stage_status,
                customer, customer_industry, description, deliverables,
                setup_date, plan_deliver_date, actual_deliver_date,
                progress_pct, risk_level, risk_desc, current_issue,
                contract_status, contract_no, contract_amount,
                invoiced_amount, received_amount, gross_margin_pct,
                owner_name, pm_name, last_update_date, form_status,
                source_filename, ingested_at
            ) VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?)
            ON CONFLICT(biz_id, snap_date) DO UPDATE SET
                project_name=excluded.project_name, biz_type=excluded.biz_type,
                stage_status=excluded.stage_status, customer=excluded.customer,
                customer_industry=excluded.customer_industry,
                description=excluded.description, deliverables=excluded.deliverables,
                setup_date=excluded.setup_date,
                plan_deliver_date=excluded.plan_deliver_date,
                actual_deliver_date=excluded.actual_deliver_date,
                progress_pct=excluded.progress_pct,
                risk_level=excluded.risk_level, risk_desc=excluded.risk_desc,
                current_issue=excluded.current_issue,
                contract_status=excluded.contract_status,
                contract_no=excluded.contract_no,
                contract_amount=excluded.contract_amount,
                invoiced_amount=excluded.invoiced_amount,
                received_amount=excluded.received_amount,
                gross_margin_pct=excluded.gross_margin_pct,
                owner_name=excluded.owner_name, pm_name=excluded.pm_name,
                last_update_date=excluded.last_update_date,
                form_status=excluded.form_status,
                source_filename=excluded.source_filename,
                ingested_at=excluded.ingested_at
            """,
            (
                p.biz_id, p.snap_date, p.project_name, p.biz_type, p.stage_status,
                p.customer, p.customer_industry, p.description, p.deliverables,
                p.setup_date, p.plan_deliver_date, p.actual_deliver_date,
                p.progress_pct, p.risk_level, p.risk_desc, p.current_issue,
                p.contract_status, p.contract_no, p.contract_amount,
                p.invoiced_amount, p.received_amount, p.gross_margin_pct,
                p.owner_name, p.pm_name, p.last_update_date, p.form_status,
                p.source_filename or "", _now_iso(),
            ),
        )

        # 子表: 先删后插, 保证幂等。biz_id/snap_date 从父 Project 注入。
        conn.execute(
            "DELETE FROM snapshot_member WHERE biz_id=? AND snap_date=?",
            (p.biz_id, p.snap_date),
        )
        conn.execute(
            "DELETE FROM snapshot_task WHERE biz_id=? AND snap_date=?",
            (p.biz_id, p.snap_date),
        )

        for m in p.members:
            conn.execute(
                """INSERT INTO snapshot_member (
                    biz_id, snap_date, row_idx, name, emp_id, role,
                    task_desc, join_start, join_end, workload_pct,
                    progress_note, eval, note, is_external
                ) VALUES (?,?,?,?,?,?, ?,?,?,?, ?,?,?,?)
                """,
                (
                    p.biz_id, p.snap_date, m.row_idx, m.name, m.emp_id,
                    m.role, m.task_desc, m.join_start, m.join_end,
                    m.workload_pct, m.progress_note, m.eval, m.note,
                    1 if m.is_external else 0,
                ),
            )

        for t in p.tasks:
            conn.execute(
                """INSERT INTO snapshot_task (
                    biz_id, snap_date, row_idx, seq, task_name,
                    owner, plan_start, plan_end, actual_start,
                    progress_pct, status, note
                ) VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?)
                """,
                (
                    p.biz_id, p.snap_date, t.row_idx, t.seq, t.task_name,
                    t.owner, t.plan_start, t.plan_end, t.actual_start,
                    t.progress_pct, t.status, t.note,
                ),
            )

        conn.commit()
        return "updated" if existed else "inserted"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 扫描批次 ─────────────────────────────────────────────

def start_scan_run(db_path: str, started_at: str = "") -> int:
    """扫描开始时插入批次行, 返回 run_id; 统计字段留空, 结束时回填。"""
    conn = get_db(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO scan_run (
                started_at, finished_at, files_total,
                inserted, updated, skipped, qc_errors, qc_warnings
            ) VALUES (?,?,?, ?,?,?, ?,?)
            """,
            (started_at, "", 0, 0, 0, 0, 0, 0),
        )
        conn.commit()
        return cur.lastrowid or 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def finalize_scan_run(run_id: int, stats: dict[str, Any], db_path: str) -> None:
    """扫描结束: 回填 finished_at 与各计数。"""
    conn = get_db(db_path)
    try:
        conn.execute(
            """UPDATE scan_run SET
                finished_at=?, files_total=?,
                inserted=?, updated=?, skipped=?,
                qc_errors=?, qc_warnings=?
            WHERE run_id=?
            """,
            (
                stats.get("finished_at", ""),
                stats.get("files_total", 0),
                stats.get("inserted", 0),
                stats.get("updated", 0),
                stats.get("skipped", 0),
                stats.get("qc_errors", 0),
                stats.get("qc_warnings", 0),
                run_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 质检写入 ─────────────────────────────────────────────

def insert_qc(issues: list[QcIssue], run_id: int, db_path: str) -> None:
    """批量写入质检问题, 每行打上 run_id(归属本次扫描)。"""
    if not issues:
        return
    conn = get_db(db_path)
    try:
        now = _now_iso()
        conn.executemany(
            """INSERT INTO qc_issue (
                run_id, biz_id, snap_date, source_filename, severity,
                issue_type, location, message, detected_at
            ) VALUES (?,?,?,?,?, ?,?,?,?)
            """,
            [
                (run_id, q.biz_id, q.snap_date, q.source_filename, q.severity,
                 q.issue_type, q.location, q.message, now)
                for q in issues
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 查询接口 ─────────────────────────────────────────────

def get_latest_projects(db_path: str) -> list[dict[str, Any]]:
    """每个 biz_id 取最新快照的主表行(01 §6 口径)。"""
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT s.* FROM snapshot s
            JOIN (
                SELECT biz_id, MAX(snap_date) AS m FROM snapshot GROUP BY biz_id
            ) t ON s.biz_id = t.biz_id AND s.snap_date = t.m
            ORDER BY s.biz_id"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_project_detail(biz_id: str, db_path: str) -> dict[str, Any] | None:
    """最新快照的主表 + members[] + tasks[]。"""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM snapshot WHERE biz_id=? ORDER BY snap_date DESC LIMIT 1",
            (biz_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        snap_date = result["snap_date"]
        members = conn.execute(
            "SELECT * FROM snapshot_member WHERE biz_id=? AND snap_date=? ORDER BY row_idx",
            (biz_id, snap_date),
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM snapshot_task WHERE biz_id=? AND snap_date=? ORDER BY row_idx",
            (biz_id, snap_date),
        ).fetchall()
        result["members"] = [dict(m) for m in members]
        result["tasks"] = [dict(t) for t in tasks]
        return result
    finally:
        conn.close()


def get_latest_members_all(db_path: str) -> list[dict[str, Any]]:
    """所有项目最新快照的非外部人员行, 含 biz_id / project_name, 供撞车分析。"""
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT m.*, s.project_name
            FROM snapshot_member m
            JOIN snapshot s ON m.biz_id = s.biz_id AND m.snap_date = s.snap_date
            JOIN (
                SELECT biz_id, MAX(snap_date) AS m FROM snapshot GROUP BY biz_id
            ) t ON s.biz_id = t.biz_id AND s.snap_date = t.m
            WHERE m.is_external = 0
            ORDER BY m.biz_id, m.row_idx"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_qc_issues(
    db_path: str, *, latest_run_only: bool = True
) -> list[dict[str, Any]]:
    """查询质检问题。latest_run_only=True → WHERE run_id = (SELECT MAX(run_id) FROM scan_run)。

    靠 run_id 精确过滤, 不得用 detected_at 时间戳硬凑。
    """
    conn = get_db(db_path)
    try:
        if latest_run_only:
            rows = conn.execute(
                """SELECT * FROM qc_issue
                WHERE run_id = (SELECT MAX(run_id) FROM scan_run)
                ORDER BY rowid"""
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM qc_issue ORDER BY rowid"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_last_scan_run(db_path: str) -> dict[str, Any] | None:
    """最近一次扫描批次记录。"""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM scan_run ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_snapshot_dates(biz_id: str, db_path: str) -> list[str]:
    """某业务的所有快照日期(二期趋势备用)。"""
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            "SELECT snap_date FROM snapshot WHERE biz_id=? ORDER BY snap_date",
            (biz_id,),
        ).fetchall()
        return [r["snap_date"] for r in rows]
    finally:
        conn.close()
