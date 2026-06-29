#!/bin/bash
# 母版同步器 GUI · 一键启动
# 双击打开终端 → 自动起 Flask 后端 → 打开浏览器
# 关闭终端窗口即停服。端口冲突自动复用。
set -e

HUB_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_DIR="$HUB_DIR/母版同步器"
URL="http://127.0.0.1:8080"

cd "$TOOL_DIR"

# ── 端口检测 ──
if lsof -i :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "▸ 端口 8080 已被占用，复用已有服务。"
else
  echo "▸ 启动 Flask 后端（127.0.0.1:8080）…"
  PYTHONPATH="." HUB_DIR="$HUB_DIR" python3 webapp/server.py &
  SERVER_PID=$!

  # 等 Flask 就绪
  for i in $(seq 1 15); do
    if curl -s "$URL" >/dev/null 2>&1; then
      echo "▸ 后端就绪。"
      break
    fi
    sleep 0.5
  done

  # 终端关闭时停服
  trap "kill $SERVER_PID 2>/dev/null; echo '▸ 后端已停。'" EXIT
fi

# ── 打开浏览器 ──
echo "▸ 打开浏览器 → $URL"
open "$URL"

echo ""
echo "══════════════════════════════════════"
echo "  母版同步器 GUI 已启动"
echo "  地址: $URL"
echo "  关闭本窗口即停止后端服务"
echo "══════════════════════════════════════"
echo ""

# 保持终端开着，显示服务器日志
wait
