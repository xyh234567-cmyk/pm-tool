#!/bin/bash
cd "$(dirname "$0")"
PYTHON=/Users/starboy/.pyenv/versions/3.12.0/bin/python3

osascript -e 'display notification "项目管理工具启动中..." with title "PM Tool"'

$PYTHON -m pip install -q -r requirements.txt 2>/dev/null

open http://127.0.0.1:8888
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
