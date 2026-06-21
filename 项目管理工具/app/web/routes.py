"""FastAPI 路由: 总览/详情/延期/撞车/质检 + 扫描触发 + 甘特 API。"""
from __future__ import annotations
from datetime import date

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.web.deps import get_db_path, get_nas_dir, get_config
from app.storage.repository import (
    get_latest_projects, get_project_detail, get_latest_members_all,
    get_qc_issues, get_last_scan_run,
)
from app.analytics.delay import (
    get_delayed_projects, get_delayed_tasks,
)
from app.analytics.resource import get_resource_conflicts
from app.analytics.dashboard import get_overview, build_project_detail

router = APIRouter()
# ── 总览 ─────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def overview(request: Request):
    cfg = get_config()
    db_path = get_db_path()
    projects = get_latest_projects(db_path)
    if not projects:
        return _render(request, "overview.html", {"rows": [], "kpi": {"total": 0, "delayed": 0, "conflict_persons": 0, "soon_deliver": 0}, "scan_run": None})

    # 收集 tasks
    tasks_by_project: dict[str, list] = {}
    for p in projects:
        detail = get_project_detail(p["biz_id"], db_path)
        tasks_by_project[p["biz_id"]] = detail["tasks"] if detail else []

    members = get_latest_members_all(db_path)
    today = date.today()
    ov = get_overview(projects, tasks_by_project, members, today, cfg["deliver_soon_days"])
    scan_run = get_last_scan_run(db_path)
    return _render(request, "overview.html", {"rows": ov["rows"], "kpi": ov["kpi"], "scan_run": scan_run})
# ── 扫描 ─────────────────────────────────────────────────

@router.post("/scan")
async def scan():
    cfg = get_config()
    db_path = get_db_path()
    nas_dir = cfg["nas_dir"]
    try:
        from app.ingest.scanner import run as scan_run
        stats = scan_run(nas_dir, db_path)
        msg = f"扫描完成: 新增{stats['inserted']} 更新{stats['updated']} 跳过{stats['skipped']}, 质检{stats['qc_errors']}错/{stats['qc_warnings']}警"
    except FileNotFoundError as e:
        msg = f"NAS 路径不可访问: {e}"
    except Exception as e:
        msg = f"扫描失败: {e}"
    # 用 flash 消息: 存在 session 或 query param 里简单做
    return RedirectResponse(url=f"/?msg={msg}", status_code=303)
# ── 详情 ─────────────────────────────────────────────────

@router.get("/project/{biz_id}", response_class=HTMLResponse)
async def project_detail(request: Request, biz_id: str):
    db_path = get_db_path()
    detail = get_project_detail(biz_id, db_path)
    if detail is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    today = date.today()
    enriched = build_project_detail(detail, detail.get("members", []), detail.get("tasks", []), today)
    return _render(request, "detail.html", {"project": enriched})
# ── 甘特 API ────────────────────────────────────────────

@router.get("/api/gantt/{biz_id}")
async def gantt_data(biz_id: str):
    db_path = get_db_path()
    detail = get_project_detail(biz_id, db_path)
    if detail is None:
        raise HTTPException(status_code=404)
    today = date.today()
    enriched = build_project_detail(detail, detail.get("members", []), detail.get("tasks", []), today)
    tasks = enriched["tasks"]
    items = [
        {
            "name": t.get("task_name", ""),
            "plan_start": t.get("plan_start"),
            "plan_end": t.get("plan_end"),
            "actual_start": t.get("actual_start"),
            "color": {"done": "#34c759", "doing": "#ff9f0a", "todo": "#aeaeb2"}.get(t.get("bar_color", "todo"), "#aeaeb2"),
        }
        for t in tasks
    ]
    return JSONResponse({"tasks": items, "domain": enriched["gantt_domain"]})
# ── 延期 ─────────────────────────────────────────────────

@router.get("/delay", response_class=HTMLResponse)
async def delay_page(request: Request):
    db_path = get_db_path()
    projects = get_latest_projects(db_path)
    tasks_by_project: dict[str, list] = {}
    for p in projects:
        detail = get_project_detail(p["biz_id"], db_path)
        tasks_by_project[p["biz_id"]] = detail["tasks"] if detail else []
    today = date.today()
    delayed_proj = get_delayed_projects(projects, tasks_by_project, today)
    delayed_task = get_delayed_tasks(projects, tasks_by_project, today)
    delayed_task.sort(key=lambda x: x["overdue_days"], reverse=True)
    return _render(request, "delay.html", {
        "delayed_projects": delayed_proj,
        "delayed_tasks": delayed_task,
    })
# ── 撞车 ─────────────────────────────────────────────────

@router.get("/resource", response_class=HTMLResponse)
async def resource_page(request: Request):
    db_path = get_db_path()
    members = get_latest_members_all(db_path)
    conflicts = get_resource_conflicts(members, date.today())
    # 数据不全的人
    incomplete = [m for m in members if not m.get("join_start") or not m.get("join_end") or m.get("workload_pct") is None]
    return _render(request, "resource.html", {
        "conflicts": conflicts,
        "incomplete": incomplete,
    })
# ── 质检 ─────────────────────────────────────────────────

@router.get("/qc", response_class=HTMLResponse)
async def qc_page(request: Request):
    db_path = get_db_path()
    issues = get_qc_issues(db_path, latest_run_only=True)
    scan_run = get_last_scan_run(db_path)
    return _render(request, "qc.html", {
        "issues": issues,
        "scan_run": scan_run,
    })
def _render(request: Request, template: str, context: dict) -> HTMLResponse:
    """服务端渲染: 使用 Jinja2 模板。"""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path
    tpl_dir = str(Path(__file__).resolve().parent / "templates")
    templates = Jinja2Templates(directory=tpl_dir)
    return templates.TemplateResponse(request, template, context)
