"""目录扫描 + 编排: 扫描 NAS 目录, 解析文件名/去重, 逐文件解析/入库。

编排流程见 03-1 §编排流程。
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.common.enums import FILENAME_PATTERN, FILENAME_DATE_FORMAT, FILENAME_IGNORE_PREFIX
from app.common.dates import parse_and_fmt
from app.common.models import QcIssue
from app.ingest.parser import parse
from app.storage.repository import (
    upsert_snapshot,
    insert_qc,
    start_scan_run,
    finalize_scan_run,
)


def parse_filename(filepath: Path) -> dict[str, Any]:
    """解析文件名, 返回元数据 dict。

    成功返回: {biz_id_from_name, name_from_name, snap_date, source_filename, mtime}
    失败也返回 dict, 但 snap_date 可能回退为 mtime, 并带 filename_format_issue。
    """
    fname = filepath.name
    meta: dict[str, Any] = {
        "source_filename": fname,
        "mtime": datetime.fromtimestamp(filepath.stat().st_mtime),
        "filename_format_issue": None,
        "biz_id_from_name": "",
        "name_from_name": "",
        "snap_date": "",
    }
    m = FILENAME_PATTERN.match(fname)
    if m:
        meta["biz_id_from_name"] = m.group("biz_id")
        meta["name_from_name"] = m.group("name")
        date_str = m.group("date")
        parsed = parse_and_fmt(
            datetime.strptime(date_str, FILENAME_DATE_FORMAT)
        )
        meta["snap_date"] = parsed or ""
    else:
        meta["filename_format_issue"] = f"文件名格式不符: {fname}, 期望 {{ID}}-{{名称}}【YYYYMMDD】.xlsx"
        # 回退到文件修改日期
        meta["snap_date"] = meta["mtime"].strftime("%Y-%m-%d")
    return meta


def _sort_key_for_dedup(meta: dict) -> float:
    """按 mtime 排序的 key(用于去重选取最新)。"""
    return meta["mtime"].timestamp()


def run(nas_dir: str, db_path: str) -> dict[str, Any]:
    """扫描 NAS 目录, 解析并入库所有 *.xlsx 文件。

    返回 stats 字典。
    """
    nas = Path(nas_dir)
    if not nas.exists() or not nas.is_dir():
        raise FileNotFoundError(f"NAS 路径不可访问: {nas_dir}")

    # 1. 启动扫描批次
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = start_scan_run(db_path, started_at=now_iso)

    # 2. 列目录, 过滤
    all_files = [
        p for p in nas.iterdir()
        if p.suffix.lower() == ".xlsx"
        and not any(p.name.startswith(prefix) for prefix in FILENAME_IGNORE_PREFIX)
    ]

    if not all_files:
        finalize_scan_run(run_id, {
            "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files_total": 0, "inserted": 0, "updated": 0,
            "skipped": 0, "qc_errors": 0, "qc_warnings": 0,
        }, db_path)
        return {"files_total": 0, "inserted": 0, "updated": 0,
                "skipped": 0, "qc_errors": 0, "qc_warnings": 0, "run_id": run_id}

    # 3. 解析文件名, 分组去重
    file_metas = [parse_filename(p) for p in all_files]
    # 按 (biz_id_from_name, snap_date) 分组
    groups: dict[tuple[str, str], list[Path]] = {}
    meta_map: dict[Path, dict] = {}
    for p, meta in zip(all_files, file_metas):
        meta_map[p] = meta
        key = (meta["biz_id_from_name"] or "__unknown__", meta["snap_date"])
        groups.setdefault(key, []).append(p)

    to_process: list[tuple[Path, dict]] = []
    skipped = 0
    for key, files in groups.items():
        if len(files) > 1:
            # 取 mtime 最新, 其余记 DUP_SNAPSHOT_FILE
            files.sort(key=lambda p: meta_map[p]["mtime"].timestamp(), reverse=True)
            for dup in files[1:]:
                insert_qc([QcIssue(
                    source_filename=dup.name,
                    severity="warning",
                    issue_type="DUP_SNAPSHOT_FILE",
                    location="文件级",
                    message=f"与 {files[0].name} 同业务同日期, 跳过",
                )], run_id, db_path)
                skipped += 1
            to_process.append((files[0], meta_map[files[0]]))
        else:
            to_process.append((files[0], meta_map[files[0]]))

    # 4. 逐文件解析入库
    inserted = 0
    updated = 0
    qc_errors = 0
    qc_warnings = 0

    for filepath, meta in to_process:
        try:
            project, issues = parse(meta, filepath)
            # 判断该文件是否可处理
            if not project.biz_id:
                qc_errors += 1
                insert_qc(issues, run_id, db_path)
                skipped += 1
                continue

            result = upsert_snapshot(project, db_path)
            if result == "inserted":
                inserted += 1
            else:
                updated += 1

            # 统计本次的 QC
            for iss in issues:
                if iss.severity == "error":
                    qc_errors += 1
                else:
                    qc_warnings += 1
            insert_qc(issues, run_id, db_path)

        except Exception as e:
            qc_errors += 1
            insert_qc([QcIssue(
                source_filename=filepath.name,
                severity="error",
                issue_type="FILE_OPEN_FAIL",
                message=f"解析异常: {e}",
            )], run_id, db_path)
            skipped += 1

    # 5. 结束扫描批次
    finalize_scan_run(run_id, {
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files_total": len(all_files),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "qc_errors": qc_errors,
        "qc_warnings": qc_warnings,
    }, db_path)

    return {
        "files_total": len(all_files),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "qc_errors": qc_errors,
        "qc_warnings": qc_warnings,
        "run_id": run_id,
    }
