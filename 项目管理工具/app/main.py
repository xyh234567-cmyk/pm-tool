"""FastAPI 入口: uvicorn app.main:app 启动。"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.web.routes import router as web_router

app = FastAPI(title="项目管理工具", version="0.1.0")

# 静态文件
static_dir = Path(__file__).resolve().parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(web_router)
