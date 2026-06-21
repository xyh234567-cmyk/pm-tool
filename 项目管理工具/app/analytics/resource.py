"""资源撞车: 扫描线算法, 口径见 03-3 §B 和 contracts/params.yaml。"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Any


def get_resource_conflicts(
    members: list[dict], today: date
) -> list[dict]:
    """计算资源撞车。

    members: 所有项目最新快照的非外部人员行(含 biz_id, project_name).
    返回按 includes_today 优先、peak_total 降序排列的撞车结果。
    """
    # 按人员名分组, 过滤缺字段的
    persons: dict[str, list[dict]] = {}
    incomplete: list[dict] = []
    for m in members:
        if not m.get("join_start") or not m.get("join_end") or m.get("workload_pct") is None:
            incomplete.append(m)
            continue
        name = m.get("name", "")
        if not name:
            continue
        persons.setdefault(name, []).append(m)

    results = []
    for name, rows in persons.items():
        if len(rows) < 2:
            continue

        intervals = []
        for r in rows:
            try:
                s = date.fromisoformat(r["join_start"])
                e = date.fromisoformat(r["join_end"])
            except (ValueError, TypeError):
                continue
            intervals.append({
                "start": s,
                "end": e,
                "workload": float(r["workload_pct"]),
                "biz_id": r["biz_id"],
                "project_name": r.get("project_name", ""),
            })

        if len(intervals) < 2:
            continue

        # 收集所有边界点
        boundaries: set[date] = set()
        for iv in intervals:
            boundaries.add(iv["start"])
            boundaries.add(iv["end"] + timedelta(days=1))  # end 是闭区间
        sorted_bounds = sorted(boundaries)

        conflict_segments = []
        for i in range(len(sorted_bounds) - 1):
            a, b = sorted_bounds[i], sorted_bounds[i + 1]
            active = [iv for iv in intervals if iv["start"] <= a and a <= iv["end"]]
            if len(active) < 2:
                continue
            total = sum(iv["workload"] for iv in active)
            if total <= 100:
                continue
            max_end = max(iv["end"] for iv in active)
            conflict_segments.append({
                "period_start": a.strftime("%Y-%m-%d"),
                "period_end": max_end.strftime("%Y-%m-%d"),
                "total": total,
                "projects": list({iv["biz_id"] for iv in active}),
                "project_names": list({iv["project_name"] for iv in active}),
                "includes_today": a <= today <= max_end,
            })

        if not conflict_segments:
            continue

        # 合并相邻/重叠冲突段, 取峰值
        peak = max(seg["total"] for seg in conflict_segments)
        includes_today = any(seg["includes_today"] for seg in conflict_segments)
        all_projects = list({p for seg in conflict_segments for p in seg["projects"]})

        results.append({
            "name": name,
            "peak_total": peak,
            "includes_today": includes_today,
            "conflict_segments": conflict_segments,
            "projects": all_projects,
        })

    # 排序: includes_today 优先, peak_total 降序
    results.sort(key=lambda r: (not r["includes_today"], -r["peak_total"]))
    return results


def count_conflict_persons(members: list[dict], today: date) -> int:
    """撞车人数(KPI 用)。"""
    return len(get_resource_conflicts(members, today))
