"""SQLite 连接管理、首次运行自动建表、简单事务封装。

依赖: 标准库 sqlite3; 配置由调用方传入 db_path。
线程安全: 单用户本地应用, 使用 check_same_thread=False。
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Generator

_SCHEMA_SQL: str | None = None
_initialized: set[str] = set()   # 已执行建表的 DB 路径集合


def _load_schema_sql() -> str:
    """延迟加载 schema.sql 文本, 避免模块导入时 IO。"""
    global _SCHEMA_SQL
    if _SCHEMA_SQL is None:
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        _SCHEMA_SQL = schema_path.read_text(encoding="utf-8")
    return _SCHEMA_SQL


def init_db(db_path: str) -> None:
    """首次运行: 创建 DB 文件、执行建表语句。

    幂等: 同一路径只建表一次(进程内)。
    """
    if db_path in _initialized:
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_load_schema_sql())
        conn.commit()
    finally:
        conn.close()
    _initialized.add(db_path)


def get_db(db_path: str) -> sqlite3.Connection:
    """获取数据库连接, 首次调用自动建表。

    调用方负责关闭连接。若需事务, 直接用 conn 的 context manager 语义。
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")  # SQLite 默认 OFF, 明确声明
    conn.execute("PRAGMA journal_mode = WAL")  # 并发读友好
    return conn
