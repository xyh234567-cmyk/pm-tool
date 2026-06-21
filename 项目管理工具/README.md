# 项目管理工具

## 启动

```bash
# 安装依赖
pip install -r requirements.txt

# 复制配置并修改
cp config.example.toml config.toml

# 启动服务
cd 项目管理工具
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

浏览器打开 `http://127.0.0.1:8000`。

## 技术栈

FastAPI + Jinja2 + ECharts + SQLite + openpyxl
