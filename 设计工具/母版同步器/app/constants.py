"""硬契约常量——照搬 contracts/*.yaml，一字不改。"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ---- 受管文件配置 ----
@dataclass(frozen=True)
class ManagedFile:
    name: str
    general_scope: str
    boundary_anchor: Optional[str] = None
    private_scope: Optional[str] = None

MANAGED_FILES = [
    ManagedFile(
        name="CLAUDE.md",
        general_scope="whole_file",
        boundary_anchor=None,
        private_scope=None,
    ),
    ManagedFile(
        name="AGENTS.md",
        general_scope="before_anchor",
        boundary_anchor="# 第二部分",
        private_scope="anchor_to_eof",
    ),
    ManagedFile(
        name="审查清单.md",
        general_scope="before_anchor",
        boundary_anchor="# 第二部分",
        private_scope="anchor_to_eof",
    ),
]

MANAGED_FILE_MAP: dict[str, ManagedFile] = {f.name: f for f in MANAGED_FILES}

# ---- 锚点匹配规则 ----
ANCHOR_MATCH_RULE = "line_startswith"
ANCHOR_PREFIX = "# 第二部分"
ANCHOR_STRIP_LEADING_WHITESPACE = False
ANCHOR_EXPECT_EXACTLY_ONE = True

# ---- 扫描范围 ----
SCAN_HUB_DIRNAME = "设计工具"
SPOKE_REQUIRED_FILES = ["CLAUDE.md", "AGENTS.md", "审查清单.md"]
EXCLUDE_DIRNAMES = ["设计工具", "历史归档"]
EXCLUDE_HIDDEN = True
RECURSE = False
INCOMPLETE_MARKER_FILES = ["审查清单.md", "AGENTS.md"]

# ---- 比对模型 ----
DIFF_UNIT = "line"
DIFF_ENGINE = "difflib"
DIFF_COMPARE = "hub_general_vs_spoke_general"
DIFF_NORMALIZE_TRAILING_WHITESPACE = False
DIFF_NORMALIZE_FINAL_NEWLINE = "keep"

# ---- 结果状态 ----
class DiffState(str, Enum):
    UP_TO_DATE = "up_to_date"
    OUTDATED = "outdated"
    STRUCTURE_ERROR = "structure_error"
    MISSING_FILE = "missing_file"

# ---- 切分结果 ----
class SplitStatus(str, Enum):
    OK = "ok"
    STRUCTURE_ERROR = "structure_error"

# ---- 应用协议 ----
APPLY_DEFAULT_MODE = "dry_run"
APPLY_REQUIRE_EXPLICIT_FLAG = True
APPLY_CONFIRMATION = "per_file"
APPLY_WHAT_GETS_WRITTEN = "replace_general_keep_private"
APPLY_BACKUP_ENABLED = True
APPLY_MUST_BACKUP_BEFORE_WRITE = True
APPLY_BACKUP_NAMING = "<原文件名>.bak.<YYYYMMDD-HHMMSS>"
APPLY_BACKUP_LOCATION = "与原文件同目录"
APPLY_REPORT_WRITE_MARKDOWN = True
APPLY_REPORT_LOCATION = "hub 根"
APPLY_REPORT_NAMING = "母版同步报告-<YYYYMMDD-HHMMSS>.md"
