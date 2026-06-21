"""dates.py 单元测试: 正例 / 异常 / 空值 / 边界。
口径以 02 §6 为准。
"""
from __future__ import annotations
from datetime import date, datetime
import pytest

from app.common.dates import (
    _coerce_date,
    parse_date,
    fmt_date,
    parse_and_fmt,
    is_date_parseable,
    days_from_today,
    today_str,
)


# ── _coerce_date · 正常解析 ───────────────────────────

def test_coerce_from_datetime():
    """openpyxl 读出 datetime → date。"""
    assert _coerce_date(datetime(2026, 6, 17, 10, 0)) == date(2026, 6, 17)


def test_coerce_from_date():
    """已是 date 对象 → 原样返回。"""
    assert _coerce_date(date(2026, 1, 1)) == date(2026, 1, 1)


@pytest.mark.parametrize("inp, expected", [
    ("2026-06-17",  date(2026, 6, 17)),
    ("2026/06/17",  date(2026, 6, 17)),
    ("20260617",   date(2026, 6, 17)),
    ("2026.06.17",  date(2026, 6, 17)),
    ("2026-01-01",  date(2026, 1, 1)),
    ("26-03-15",    date(2026, 3, 15)),       # %y-%m-%d
])
def test_coerce_string_normal(inp, expected):
    assert _coerce_date(inp) == expected


@pytest.mark.parametrize("inp, expected", [
    ("2026/4/16",   date(2026, 4, 16)),       # 非零填充
    ("2026-4-5",    date(2026, 4, 5)),
    ("2026.4.5",    date(2026, 4, 5)),
])
def test_coerce_non_zero_padded(inp, expected):
    """strptime 匹配不上的非零填充格式, 走拆分解析。"""
    assert _coerce_date(inp) == expected


# ── _coerce_date · 异常 / 空值 ─────────────────────────

@pytest.mark.parametrize("inp", [
    None,
    "",
    "   ",
    "abc",
    "2026-13-01",
    "2026-02-30",
    "not-a-date",
    "2026",
])
def test_coerce_invalid_returns_none(inp):
    assert _coerce_date(inp) is None


def test_coerce_int_float_returns_none():
    """Excel 序列号暂不支持, 返回 None。"""
    assert _coerce_date(45000) is None
    assert _coerce_date(3.14) is None


# ── parse_date / parse_and_fmt ─────────────────────────

def test_parse_date_delegates():
    assert parse_date("2026-06-17") == date(2026, 6, 17)
    assert parse_date(None) is None


@pytest.mark.parametrize("inp, expected", [
    (datetime(2026, 6, 17), "2026-06-17"),
    (date(2026, 1, 1),     "2026-01-01"),
    ("2026-06-17",         "2026-06-17"),
    ("2026/4/16",          "2026-04-16"),
    (None,                 None),
    ("",                   None),
    ("xxx",                 None),
])
def test_parse_and_fmt(inp, expected):
    assert parse_and_fmt(inp) == expected


# ── fmt_date ────────────────────────────────────────────

def test_fmt_date_valid():
    assert fmt_date(date(2026, 12, 31)) == "2026-12-31"


def test_fmt_date_none():
    assert fmt_date(None) is None


# ── is_date_parseable ──────────────────────────────────

@pytest.mark.parametrize("inp, ok", [
    ("2026-01-01", True),
    ("2026/4/16",  True),
    ("",           False),
    ("nope",       False),
    (None,         False),
])
def test_is_date_parseable(inp, ok):
    assert is_date_parseable(inp) is ok


# ── days_from_today ────────────────────────────────────

def test_days_from_today_past():
    """给定日期在过去, 返回正数。"""
    frozen = date(2026, 6, 20)
    assert days_from_today("2026-06-15", today=frozen) == 5


def test_days_from_today_future():
    """给定日期在未来, 返回负数。"""
    frozen = date(2026, 6, 10)
    assert days_from_today("2026-06-15", today=frozen) == -5


def test_days_from_today_today():
    """当天返回 0。"""
    frozen = date(2026, 6, 15)
    assert days_from_today("2026-06-15", today=frozen) == 0


def test_days_from_today_none_input():
    assert days_from_today(None) is None


def test_days_from_today_invalid_str():
    assert days_from_today("abc") is None


def test_days_from_today_leap_year():
    """闰年日期, 2024-02-29 可解析。"""
    frozen = date(2024, 3, 1)
    assert days_from_today("2024-02-29", today=frozen) == 1


# ── today_str ──────────────────────────────────────────

def test_today_str_format():
    t = today_str()
    # 格式 YYYY-MM-DD, 长度 10
    assert len(t) == 10
    assert t[4] == "-" and t[7] == "-"
    # 能解析回来
    assert parse_date(t) is not None
