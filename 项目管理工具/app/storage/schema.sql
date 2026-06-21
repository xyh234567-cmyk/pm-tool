-- 建表 DDL · 照搬 contracts/db_schema.yaml
-- 冲突以 YAML 为准; 日期 YYYY-MM-DD 文本存, 金额/百分比 REAL, 空值 NULL

CREATE TABLE IF NOT EXISTS snapshot (
    biz_id              TEXT NOT NULL,
    snap_date           TEXT NOT NULL,
    project_name        TEXT,
    biz_type            TEXT,
    stage_status        TEXT,
    customer            TEXT,
    customer_industry   TEXT,
    description         TEXT,
    deliverables        TEXT,
    setup_date          TEXT,
    plan_deliver_date   TEXT,
    actual_deliver_date TEXT,
    progress_pct        REAL,
    risk_level          TEXT,
    risk_desc           TEXT,
    current_issue       TEXT,
    contract_status     TEXT,
    contract_no         TEXT,
    contract_amount     REAL,
    invoiced_amount     REAL,
    received_amount     REAL,
    gross_margin_pct    REAL,
    owner_name          TEXT,
    pm_name             TEXT,
    last_update_date    TEXT,
    form_status         TEXT,
    source_filename     TEXT,
    ingested_at         TEXT,
    PRIMARY KEY (biz_id, snap_date)
);

CREATE TABLE IF NOT EXISTS snapshot_member (
    biz_id        TEXT NOT NULL,
    snap_date     TEXT NOT NULL,
    row_idx       INTEGER NOT NULL,
    name          TEXT,
    emp_id        TEXT,
    role          TEXT,
    task_desc     TEXT,
    join_start    TEXT,
    join_end      TEXT,
    workload_pct  REAL,
    progress_note TEXT,
    eval          TEXT,
    note          TEXT,
    is_external   INTEGER DEFAULT 0,
    PRIMARY KEY (biz_id, snap_date, row_idx)
);

CREATE TABLE IF NOT EXISTS snapshot_task (
    biz_id       TEXT NOT NULL,
    snap_date    TEXT NOT NULL,
    row_idx      INTEGER NOT NULL,
    seq          TEXT,
    task_name    TEXT,
    owner        TEXT,
    plan_start   TEXT,
    plan_end     TEXT,
    actual_start TEXT,
    progress_pct REAL,
    status       TEXT,
    note         TEXT,
    PRIMARY KEY (biz_id, snap_date, row_idx)
);

CREATE TABLE IF NOT EXISTS qc_issue (
    run_id          INTEGER,
    biz_id          TEXT,
    snap_date       TEXT,
    source_filename TEXT,
    severity        TEXT,
    issue_type      TEXT,
    location        TEXT,
    message         TEXT,
    detected_at     TEXT
);

CREATE TABLE IF NOT EXISTS scan_run (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    files_total INTEGER,
    inserted    INTEGER,
    updated     INTEGER,
    skipped     INTEGER,
    qc_errors   INTEGER,
    qc_warnings INTEGER
);

CREATE INDEX IF NOT EXISTS idx_snapshot_latest ON snapshot(biz_id, snap_date);
CREATE INDEX IF NOT EXISTS idx_member_person   ON snapshot_member(name, snap_date);
CREATE INDEX IF NOT EXISTS idx_task_proj       ON snapshot_task(biz_id, snap_date);
