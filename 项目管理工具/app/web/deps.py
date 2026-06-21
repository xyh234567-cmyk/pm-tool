"""FastAPI 依赖注入: config / db_path。"""
from __future__ import annotations
from pathlib import Path

from app.config import load_config

_config: dict | None = None


def get_config() -> dict:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_db_path() -> str:
    return str(get_config()["db_path"])


def get_nas_dir() -> str:
    return str(get_config()["nas_dir"])
