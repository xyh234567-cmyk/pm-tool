"""webapp 路由测试——验收用例 7-10"""
import os
import json
import pytest


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _make_hub_spoke(tmpdir):
    """造一套 hub + spoke 合成目录。spoke 通用区与 hub 不同（制造 outdated）。"""
    root = str(tmpdir / "设计")
    hub_dir = os.path.join(root, "设计工具")
    spoke_dir = os.path.join(root, "产品规划")

    hub_claude = "# hub CLAUDE\n通用区内容。\n"
    hub_agents = "# hub AGENTS\n\n# 第一部分\n通用规则。\n\n# 第二部分\nhub 专属。\n"
    hub_checklist = "# 审查清单\n\n# 第一部分\n通用审查项。\n\n# 第二部分\n\n- **L1 · 符号方向**:内容。\n"

    _write(os.path.join(hub_dir, "CLAUDE.md"), hub_claude)
    _write(os.path.join(hub_dir, "AGENTS.md"), hub_agents)
    _write(os.path.join(hub_dir, "审查清单.md"), hub_checklist)

    # spoke CLAUDE 版本不同 → outdated
    _write(os.path.join(spoke_dir, "CLAUDE.md"), "# spoke CLAUDE\n旧版本内容。\n")
    _write(os.path.join(spoke_dir, "AGENTS.md"), hub_agents)
    _write(os.path.join(spoke_dir, "审查清单.md"), hub_checklist)

    return hub_dir, spoke_dir


@pytest.fixture
def app(tmpdir):
    """创建 Flask 测试 app，注入合成 hub_dir。"""
    hub_dir, _ = _make_hub_spoke(tmpdir)
    os.environ["HUB_DIR"] = hub_dir
    from webapp.server import create_app
    application = create_app(hub_dir)
    application.config["TESTING"] = True
    yield application
    os.environ.pop("HUB_DIR", None)


class TestPages:
    """用例7: GET / 返回页面"""

    def test_index_page(self, app):
        client = app.test_client()
        rv = client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "母版同步器" in html
        assert "通用区下发" in html or "tab" in html.lower()


class TestApiScan:
    """用例8: GET /api/scan 返回结构化 JSON"""

    def test_scan_general_returns_json(self, app):
        client = app.test_client()
        rv = client.get("/api/scan?mode=general")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert isinstance(data, list)
        # 应有 产品规划 的 3 个文件
        spoke_items = [r for r in data if r["spoke_name"] == "产品规划"]
        assert len(spoke_items) >= 1

        claude = [r for r in spoke_items if r["file_name"] == "CLAUDE.md"]
        assert len(claude) == 1
        assert claude[0]["state"] == "outdated"
        assert claude[0]["diff_text"]


class TestApiApply:
    """用例9-10: POST /api/apply 写入 + 拒绝非法项"""

    def test_apply_writes_and_creates_backup(self, app, tmpdir):
        """用例9: 写一个合法 outdated 项 → 文件改、备份存在。"""
        client = app.test_client()

        # 先扫描确认 outdated
        scan_rv = client.get("/api/scan?mode=general")
        scan_data = json.loads(scan_rv.data)
        outdated = [r for r in scan_data if r["can_apply"]]
        assert len(outdated) >= 1

        # 执行写入
        apply_rv = client.post("/api/apply",
            data=json.dumps({"mode": "general", "items": [{
                "spoke_name": outdated[0]["spoke_name"],
                "file_name": outdated[0]["file_name"],
            }]}),
            content_type="application/json")
        assert apply_rv.status_code == 200
        apply_data = json.loads(apply_rv.data)
        assert len(apply_data) == 1
        assert apply_data[0]["success"] is True
        assert apply_data[0]["backup_path"]
        assert os.path.isfile(apply_data[0]["backup_path"])

        # 验证文件已改
        spoke_dir = os.path.join(tmpdir, "设计", "产品规划")
        spoke_file = os.path.join(spoke_dir, outdated[0]["file_name"])
        content = open(spoke_file, encoding="utf-8").read()
        assert "通用区内容" in content

    def test_apply_rejects_non_writable(self, app):
        """用例10: 传不可写项 → 被拒、文件不变。"""
        client = app.test_client()
        apply_rv = client.post("/api/apply",
            data=json.dumps({"mode": "general", "items": [{
                "spoke_name": "产品规划",
                "file_name": "AGENTS.md",
            }]}),
            content_type="application/json")
        assert apply_rv.status_code == 200
        apply_data = json.loads(apply_rv.data)
        assert apply_data[0]["success"] is False


class TestCreateProject:
    """07 新建项目路由: 用例 5-7"""

    def test_create_project_ok(self, app, tmpdir):
        client = app.test_client()
        name = "新项目ABC"
        rv = client.post("/api/create-project",
            data=json.dumps({"name": name}),
            content_type="application/json")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["success"] is True
        assert data["project_dir"]
        assert len(data["created_files"]) == 6
        assert os.path.isdir(data["project_dir"])

    def test_create_project_duplicate_rejected(self, app, tmpdir):
        client = app.test_client()
        client.post("/api/create-project",
            data=json.dumps({"name": "测试项目"}),
            content_type="application/json")
        rv = client.post("/api/create-project",
            data=json.dumps({"name": "测试项目"}),
            content_type="application/json")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["success"] is False
        assert "已存在" in data.get("error", "")

    def test_index_has_new_project_tab(self, app):
        client = app.test_client()
        rv = client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "新建项目" in html
        assert "同步母版" in html
