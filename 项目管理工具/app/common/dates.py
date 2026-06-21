"""日期解析与计算工具。口径见 02-数据模型与Excel解析规格 §6。

规则:
- openpyxl 读出 datetime/date → 取 .date(), 格式化为 "YYYY-MM-DD"
- 字符串 "2026-04-16" / "2026/4/16" → 尽力解析为 date
- 解析失败 → 返回 None(调用方记 BAD_DATE 告警)
- 空 / None → None
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any

# 尝试多种日期字符串格式
_STR_FMTS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%Y.%m.%d",
    "%y-%m-%d",
]


def _coerce_date(value: Any) -> date | None:
    """将任意输入尽力转为 date 对象; 失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return None  # Excel 序列号暂不支持
    s = str(value).strip()
    if not s:
        return None
    for fmt in _STR_FMTS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # 处理 "2026/4/16" 这类非零填充格式
    parts = s.replace("/", "-").replace(".", "-")
    try:
        if parts.count("-") == 2:
            bits = parts.split("-")
            return date(int(bits[0]), int(bits[1]), int(bits[2]))
    except (ValueError, IndexError):
        pass
    return None


def parse_date(value: Any) -> date | None:
    """解析为 Python date 对象。按 §6 规则处理。"""
    return _coerce_date(value)


def fmt_date(d: date | None) -> str | None:
    """date → "YYYY-MM-DD"。"""
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")


def parse_and_fmt(value: Any) -> str | None:
    """解析 + 格式化: 输入任意 → 输出 "YYYY-MM-DD" 或 None。这是最常用的组合。"""
    return fmt_date(_coerce_date(value))


def is_date_parseable(value: Any) -> bool:
    """是否可解析为日期, 供 QC 判断用。"""
    return _coerce_date(value) is not None


def days_from_today(date_str: str | None, *, today: date | None = None) -> int | None:
    """计算给定日期距离今天的天数(正数=已过去, 负数=未来)。

    用于"距交付"等计算。date_str 须为 "YYYY-MM-DD" 格式(已由 parse_and_fmt 保证)。
    返回 None 表示给定日期无效。
    """
    if date_str is None:
        return None
    d = _coerce_date(date_str)
    if d is None:
        return None
    t = today or date.today()
    return (t - d).days


def today_str() -> str:
    """当前日期字符串 "YYYY-MM-DD"。"""
    return date.today().strftime("%Y-%m-%d")
