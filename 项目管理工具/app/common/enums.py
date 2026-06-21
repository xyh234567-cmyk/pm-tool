"""枚举与硬常量 —— 照搬 contracts/enums.yaml。

命名: YAML key 的下划线形式 → Python 常量(大写)。
"""
from __future__ import annotations
import re

# ── 业务ID ──────────────────────────────────────────────
BIZ_ID_PATTERN = re.compile(r"^RW\d{4}-\d{3}$")
BIZ_ID_EXAMPLE = "RW2026-001"

# ── 文件名规则 ──────────────────────────────────────────
FILENAME_PATTERN = re.compile(r"^(?P<biz_id>.+?)-(?P<name>.+?)【(?P<date>\d{8})】\.xlsx$")
FILENAME_DATE_FORMAT = "%Y%m%d"
FILENAME_IGNORE_PREFIX = ["~$"]           # 临时锁文件, 扫描跳过

# ── 质检严重度 ──────────────────────────────────────────
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# ── 质检问题类型 → 默认严重度 ───────────────────────────
QC_ISSUE_SEVERITY: dict[str, str] = {
    "FILE_OPEN_FAIL":           "error",
    "SHEET_MISSING":            "warning",
    "BIZ_ID_MISSING":           "error",
    "BIZ_ID_FORMAT":            "warning",
    "ID_FILENAME_MISMATCH":     "warning",
    "REQUIRED_EMPTY":           "warning",
    "BAD_DATE":                 "warning",
    "BAD_NUMBER":               "warning",
    "MEMBER_EXTERNAL":          "warning",
    "MULTI_NAME_IN_MEMBER":     "warning",
    "WORKLOAD_MISSING":         "warning",
    "DUP_SNAPSHOT_FILE":        "warning",
    "FILENAME_FORMAT":          "warning",
}

# ── 非真实人员取值 → is_external=1, 不参与撞车 ─────────
EXTERNAL_MEMBER_NAMES: set[str] = {"外协", "?", "？", ""}

# ── 人员姓名一格多名字的分隔符 ──────────────────────────
MEMBER_NAME_SEPARATORS = ["\n", "、", "，", ",", "/"]

# ── 任务状态 → 甘特颜色 ────────────────────────────────
TASK_STATUS_COLOR: dict[str, set[str]] = {
    "done":  {"已完成", "完成"},
    "doing": {"进行中", "部分完成"},
    "todo":  {"未开始", ""},
}

# ── 延期判定"已完成"集合 ────────────────────────────────
DONE_STATUSES: set[str] = {"已完成", "完成"}

# ── 风险等级(展示标签) ─────────────────────────────────
RISK_LEVELS: list[str] = ["低风险", "中风险", "高风险"]
