"""数据类: dataclass 映射, 字段一一对齐 contracts/db_schema.yaml。

命名: 表名 snapshot_* → 类名去 snapshot_ 前缀, 便于业务代码使用。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Project:
    """对应 snapshot 主表一行 —— 某业务在某快照日期的完整信息。"""
    biz_id: str
    snap_date: str
    project_name: str | None = None
    biz_type: str | None = None
    stage_status: str | None = None
    customer: str | None = None
    customer_industry: str | None = None
    description: str | None = None
    deliverables: str | None = None
    setup_date: str | None = None
    plan_deliver_date: str | None = None
    actual_deliver_date: str | None = None
    progress_pct: float | None = None
    risk_level: str | None = None
    risk_desc: str | None = None
    current_issue: str | None = None
    contract_status: str | None = None
    contract_no: str | None = None
    contract_amount: float | None = None
    invoiced_amount: float | None = None
    received_amount: float | None = None
    gross_margin_pct: float | None = None
    owner_name: str | None = None
    pm_name: str | None = None
    last_update_date: str | None = None
    form_status: str | None = None
    source_filename: str | None = None
    ingested_at: str | None = None
    # 关联子表(不入库, 内存组装用)
    members: list[Member] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)


@dataclass
class Member:
    """对应 snapshot_member 表一行。"""
    # 联合主键: biz_id + snap_date + row_idx
    row_idx: int = 0
    name: str | None = None
    emp_id: str | None = None
    role: str | None = None
    task_desc: str | None = None
    join_start: str | None = None
    join_end: str | None = None
    workload_pct: float | None = None
    progress_note: str | None = None
    eval: str | None = None
    note: str | None = None
    is_external: bool = False           # 外协/非真实人员 → 不参与撞车


@dataclass
class Task:
    """对应 snapshot_task 表一行。"""
    # 联合主键: biz_id + snap_date + row_idx
    row_idx: int = 0
    seq: str | None = None              # 原表 "#" 列
    task_name: str | None = None
    owner: str | None = None
    plan_start: str | None = None
    plan_end: str | None = None
    actual_start: str | None = None
    progress_pct: float | None = None
    status: str | None = None
    note: str | None = None


@dataclass
class QcIssue:
    """对应 qc_issue 表一行。"""
    biz_id: str | None = None
    snap_date: str | None = None
    source_filename: str = ""
    severity: str = "warning"            # error | warning
    issue_type: str = ""
    location: str = ""
    message: str = ""
