"""FastAPI 入口: uvicorn app.main:app 启动。"""
from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="项目管理工具", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> str:
    """首页占位 —— 阶段 0 脚手架验证通过后,阶段 5 替换为完整视图。"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>项目管理工具</title>
<style>
  body { font-family: -apple-system, "PingFang SC", sans-serif; display: flex;
         justify-content: center; align-items: center; min-height: 100vh;
         margin: 0; background: #f5f5f5; color: #333; }
  main { text-align: center; }
  h1 { font-weight: 500; margin: 0 0 8px; }
  p { color: #888; }
</style>
</head>
<body>
<main>
  <h1>项目管理工具</h1>
  <p>脚手架阶段 · 服务已启动</p>
</main>
</body>
</html>"""
