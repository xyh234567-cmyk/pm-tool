"""模板映射常量 —— 照搬 contracts/excel_template.yaml。

区块锚点、标签归一规则、键值字段映射、表头关键词、类型转换规则。
"""
from __future__ import annotations
import re

# ── Sheet ───────────────────────────────────────────────
PRIMARY_SHEET = "业务填写表"
IGNORE_SHEETS = {"字典参考"}
DATA_ONLY = True

# ── 区块锚点(A 列扫描) ─────────────────────────────────
SECTION_ANCHORS = {
    "basic": "一、业务基本信息",
    "contract": "二、合同与经营信息",
    "members": "三、人员分工",
    "tasks": "四、阶段",
}
ANCHOR_TEXTS = list(SECTION_ANCHORS.values())

# ── 标签归一 ────────────────────────────────────────────
LABEL_STRIP_CHARS = "★ 　"
# 末尾括号内容正则: (元) (员工ID) 等
_LABEL_PAREN_RE = re.compile(r"[(（][^)）]*[)）]$")


def normalize_label(raw: str) -> str:
    """标签归一: 去首尾空白/★/全角空格, 去末尾括注, 收缩内部空白。"""
    s = raw.strip(LABEL_STRIP_CHARS)
    s = _LABEL_PAREN_RE.sub("", s).strip()
    # 收缩内部空白: 连续空白→单个空格, 去斜杠/圆点周围空格
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return s


# ── 键值字段映射(区块一/二) ─────────────────────────────
KEY_VALUE_FIELDS: dict[str, dict] = {
    "业务ID":            {"column": "biz_id",            "type": "text",   "required": True},
    "业务类型":          {"column": "biz_type",          "type": "text"},
    "当前阶段/状态":     {"column": "stage_status",      "type": "text",   "required": True},
    "业务名称":          {"column": "project_name",      "type": "text",   "required": True},
    "客户名称":          {"column": "customer",          "type": "text"},
    "客户行业":          {"column": "customer_industry", "type": "text"},
    "业务描述/一句话说明": {"column": "description",      "type": "text"},
    "关键任务/交付内容": {"column": "deliverables",      "type": "text"},
    "立项日期":          {"column": "setup_date",        "type": "date"},
    "计划交付日期":      {"column": "plan_deliver_date", "type": "date"},
    "实际交付日期":      {"column": "actual_deliver_date", "type": "date"},
    "完成度%":           {"column": "progress_pct",      "type": "number", "required": True},
    "风险等级":          {"column": "risk_level",        "type": "text"},
    "风险描述/难点":     {"column": "risk_desc",         "type": "text"},
    "当前主要问题":      {"column": "current_issue",     "type": "text"},
    "合同状态":          {"column": "contract_status",   "type": "text"},
    "合同编号":          {"column": "contract_no",       "type": "text"},
    "合同金额":          {"column": "contract_amount",   "type": "number"},
    "已开票金额":        {"column": "invoiced_amount",   "type": "number"},
    "已回款金额":        {"column": "received_amount",   "type": "number"},
    "毛利率%估算":       {"column": "gross_margin_pct",  "type": "number"},
    "项目总负责人":      {"column": "owner_name",        "type": "text"},
    "项目经理":          {"column": "pm_name",           "type": "text"},
    "最后更新日期":      {"column": "last_update_date",  "type": "date"},
    "表单状态":          {"column": "form_status",       "type": "text"},
}

# ── 人员分工表头映射 ────────────────────────────────────
MEMBER_HEADER_DETECT = ["姓名", "投入工作量"]
MEMBER_COLUMN_MAP = {
    "姓名": "name",
    "员工ID": "emp_id",
    "角色": "role",
    "具体负责任务": "task_desc",
    "参与开始": "join_start",
    "参与结束": "join_end",
    "投入工作量%": "workload_pct",
    "当前完成情况": "progress_note",
    "上级评价": "eval",
    "备注": "note",
}

# ── 任务表头映射 ────────────────────────────────────────
TASK_HEADER_DETECT = ["#", "计划开始"]
TASK_COLUMN_MAP = {
    "#": "seq",
    "阶段/任务名称": "task_name",
    "负责人": "owner",
    "计划开始": "plan_start",
    "计划结束": "plan_end",
    "实际开始": "actual_start",
    "完成度%": "progress_pct",
    "状态": "status",
    "备注": "note",
}
