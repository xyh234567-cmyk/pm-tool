#!/bin/bash
# 项目管理工具 · 一键启动
cd "$(dirname "$0")"
PYTHON=/Users/starboy/.pyenv/versions/3.12.0/bin/python3

echo ">>> 安装依赖..."
$PYTHON -m pip install -q -r requirements.txt 2>/dev/null

echo ">>> 启动服务: http://127.0.0.1:8888"
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
