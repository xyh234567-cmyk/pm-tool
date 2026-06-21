"""ingest 模块单元测试: 文件名解析、parser 解析 4 区块、去重、QC。"""
from __future__ import annotations
import os
import tempfile
import shutil
from pathlib import Path
import pytest

from app.ingest.scanner import parse_filename, run as scan_run
from app.ingest.parser import parse, _parse_number
from app.ingest.template_map import normalize_label

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_pm_")
    os.close(fd)
    from app.storage.db import init_db
    init_db(path)
    yield path
    try:
        Path(path).unlink()
        for s in ("-wal", "-shm"):
            Path(path + s).unlink(missing_ok=True)
    except OSError:
        pass


@pytest.fixture
def fixture_dir():
    tmp = tempfile.mkdtemp(prefix="test_nas_")
    tp = Path(tmp)
    for f in FIXTURES.iterdir():
        shutil.copy2(f, tp / f.name)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ── 文件名解析 ──────────────────────────────────────────

def test_parse_filename_normal():
    meta = parse_filename(FIXTURES / "RW2026-001-隔离网关【20260617】.xlsx")
    assert meta["biz_id_from_name"] == "RW2026-001"
    assert meta["name_from_name"] == "隔离网关"
    assert meta["snap_date"] == "2026-06-17"
    assert meta["filename_format_issue"] is None


def test_parse_filename_old_format():
    meta = parse_filename(FIXTURES / "BIZ-125-隔离网关【20260617】.xlsx")
    assert meta["biz_id_from_name"] == "BIZ-125"
    assert meta["snap_date"] == "2026-06-17"


# ── 标签归一 ────────────────────────────────────────────

def test_normalize_label():
    assert normalize_label("业务ID") == "业务ID"
    assert normalize_label("★业务ID") == "业务ID"
    assert normalize_label(" 当前阶段 / 状态 ") == "当前阶段/状态"
    assert normalize_label("合同金额(元)") == "合同金额"


# ── 数字解析 ────────────────────────────────────────────

def test_parse_number():
    assert _parse_number(65) == 65.0
    assert _parse_number("65%") == 65.0
    assert _parse_number(None) is None


# ── parser 解析(新键值逻辑: 逐行扫描所有列) ─────────────

def test_parse_standard_file():
    """标准格式: 验证主表所有字段 + 次列标签(D/E列)被正确解析。"""
    filepath = FIXTURES / "RW2026-001-隔离网关【20260617】.xlsx"
    meta = parse_filename(filepath)
    project, issues = parse(meta, filepath)

    # 主键
    assert project.biz_id == "RW2026-001"
    assert project.snap_date == "2026-06-17"

    # A列标签 + 紧邻值
    assert project.project_name == "隔离网关项目"
    assert project.customer == "吉通力/成都核动力院"
    assert project.setup_date == "2026-04-16"
    assert project.progress_pct == 65.0
    assert project.owner_name == "刘长城"
    assert project.last_update_date == "2026-06-17"
    assert project.form_status == "填写中"

    # D/E列标签(次列) — 旧解析器拿不到这些
    assert project.biz_type == "研制项目", f"biz_type expected '研制项目', got {project.biz_type}"
    assert project.customer_industry == "智能制造", f"customer_industry got {project.customer_industry}"
    assert project.plan_deliver_date == "2026-06-15", f"plan_deliver_date got {project.plan_deliver_date}"
    assert project.risk_level == "低风险", f"risk_level got {project.risk_level}"
    assert project.pm_name == "徐裕蘅", f"pm_name got {project.pm_name}"

    # 存在但值为空的标签
    assert project.stage_status == "进行中"
    assert project.contract_status is None
    assert project.contract_no is None
    assert project.contract_amount is None
    assert project.received_amount is None
    assert project.gross_margin_pct is None
    assert project.actual_deliver_date is None

    # 子表
    assert len(project.members) > 0
    assert len(project.tasks) > 0


def test_parse_old_format_file():
    """旧格式: biz_id=125 → BIZ_ID_FORMAT + ID_FILENAME_MISMATCH。"""
    filepath = FIXTURES / "BIZ-125-隔离网关【20260617】.xlsx"
    meta = parse_filename(filepath)
    project, issues = parse(meta, filepath)

    biz_format = [i for i in issues if i.issue_type == "BIZ_ID_FORMAT"]
    assert len(biz_format) >= 1, f"issues: {[(i.issue_type,i.message) for i in issues]}"

    mismatches = [i for i in issues if i.issue_type == "ID_FILENAME_MISMATCH"]
    assert len(mismatches) >= 1

    assert len(project.members) > 0
    assert len(project.tasks) > 0


def test_parse_all_kv_fields_from_fixture():
    """逐行扫描所有列后, 应比对的真实字段值清单。"""
    filepath = FIXTURES / "RW2026-001-隔离网关【20260617】.xlsx"
    meta = parse_filename(filepath)
    project, _ = parse(meta, filepath)

    expected = {
        "biz_id": "RW2026-001",
        "project_name": "隔离网关项目",
            "biz_type": "研制项目",
            "stage_status": "进行中",
            "customer": "吉通力/成都核动力院",
        "customer_industry": "智能制造",
        "description": "为成都核动力院研制定制化隔离网关设备，含嵌入式软件开发",
        "setup_date": "2026-04-16",
        "plan_deliver_date": "2026-06-15",
        "actual_deliver_date": None,
        "progress_pct": 65.0,
        "risk_level": "低风险",
        "current_issue": None,
        "contract_status": None,
        "contract_no": None,
        "contract_amount": None,
        "invoiced_amount": None,
        "received_amount": None,
        "gross_margin_pct": None,
        "owner_name": "刘长城",
        "pm_name": "徐裕蘅",
        "last_update_date": "2026-06-17",
        "form_status": "填写中",
    }
    for field, want in expected.items():
        got = getattr(project, field)
        assert got == want, f"Field {field}: expected {want!r}, got {got!r}"


# ── scanner 编排 ────────────────────────────────────────

def test_scan_run_integration(fixture_dir, db_path):
    from app.storage.repository import get_latest_projects, get_qc_issues
    stats = scan_run(str(fixture_dir), db_path)
    assert stats["files_total"] == 2
    assert stats["inserted"] + stats["updated"] >= 1
    assert len(get_latest_projects(db_path)) >= 1
    assert len(get_qc_issues(db_path, latest_run_only=False)) > 0


def test_scan_empty_dir(db_path):
    tmp = tempfile.mkdtemp(prefix="empty_nas_")
    try:
        stats = scan_run(tmp, db_path)
        assert stats["files_total"] == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_scan_nas_not_found(db_path):
    with pytest.raises(FileNotFoundError):
        scan_run("/nonexistent/path/nas", db_path)


def test_dup_same_biz_date(db_path):
    src = FIXTURES / "RW2026-001-隔离网关【20260617】.xlsx"
    tmp = tempfile.mkdtemp(prefix="dup_nas_")
    tp = Path(tmp)
    try:
        shutil.copy2(src, tp / "RW2026-001-隔离网关【20260617】.xlsx")
        import time; time.sleep(0.06)
        shutil.copy2(src, tp / "RW2026-001-隔离网关副本【20260617】.xlsx")
        stats = scan_run(str(tp), db_path)
        assert stats["inserted"] + stats["updated"] == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
