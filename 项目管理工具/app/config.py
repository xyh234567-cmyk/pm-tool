"""配置加载:从 config.toml 读取 NAS 路径、数据库路径、阈值等。

Python 3.11+ 内置 tomllib, 无需额外依赖。
"""
from __future__ import annotations
import os
from pathlib import Path

# 配置根目录:app/ 的上一级(即项目管理工具/)
CONFIG_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CONFIG_DIR / "config.toml"
EXAMPLE_CONFIG = CONFIG_DIR / "config.example.toml"


def load_config(config_path: Path | None = None) -> dict:
    """读取 TOML 配置, 不存在时回退到 config.example.toml。"""
    path = config_path or DEFAULT_CONFIG
    if not path.exists():
        path = EXAMPLE_CONFIG
    import tomllib
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    paths = raw.get("paths", {})
    thresholds = raw.get("thresholds", {})
    server = raw.get("server", {})

    return {
        "nas_dir": paths.get("nas_dir", ""),
        "db_path": str(CONFIG_DIR / paths.get("db_path", "data/pm.db")),
        "deliver_soon_days": int(thresholds.get("deliver_soon_days", "7")),
        "workload_conflict_pct": int(thresholds.get("workload_conflict_pct", "100")),
        "host": server.get("host", "127.0.0.1"),
        "port": int(server.get("port", "8000")),
    }
