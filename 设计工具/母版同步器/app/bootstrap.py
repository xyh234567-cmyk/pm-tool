"""bootstrap · 唯一建项目实现
新建 spoke: 从 hub 拷母版 + 建档案骨架。
"""
import os
import shutil
from dataclasses import dataclass, field


@dataclass
class CreateResult:
    success: bool
    project_dir: str = ""
    created_files: list[str] = field(default_factory=list)
    error: str = ""


def create_project(root_dir: str, name: str) -> CreateResult:
    """在 root_dir 下新建项目目录，拷贝 hub 母版并生成骨架。"""
    if not name or not name.strip():
        return CreateResult(success=False, error="项目名不能为空")
    name = name.strip()

    hub_dir = os.path.join(root_dir, "设计工具")
    project_dir = os.path.join(root_dir, name)

    # 1. 同名已存在则拒绝
    if os.path.exists(project_dir):
        return CreateResult(success=False, error=f"项目已存在: {project_dir}(同名已存在，拒绝覆盖)")

    # 2. 校验 hub 三件套
    managed = ["CLAUDE.md", "AGENTS.md", "审查清单.md"]
    for fname in managed:
        if not os.path.isfile(os.path.join(hub_dir, fname)):
            return CreateResult(success=False, error=f"hub 缺母版 {fname}")

    # 3. 建目录骨架
    try:
        os.makedirs(os.path.join(project_dir, "specs", "contracts"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "specs", "mockups"), exist_ok=True)
    except OSError as e:
        return CreateResult(success=False, error=f"建目录失败: {e}")

    created: list[str] = []

    # 4. 拷贝三件套
    for fname in managed:
        dst = os.path.join(project_dir, fname)
        shutil.copy2(os.path.join(hub_dir, fname), dst)
        created.append(fname)

    # 5. 生成骨架文件
    skeletons = {
        "决策记录.md": (
            f"# 决策记录 · {name}(append-only)\n\n"
            "> 仅记本项目口径与取舍。方法论通用决策在 hub(设计工具/)。每条:决定了什么 / 为什么 / 日期。\n"
        ),
        "路线图.md": (
            f"# 路线图 / 需求池 · {name}\n\n"
            "> 新念头先进这里,不当场塞进当前阶段。状态:[池] [二期] [做中] [已交付]\n\n"
            "## 当前阶段\n\n## 二期及以后\n"
        ),
        "specs/00-总览.md": (
            f"# 00 · 总览 · {name}\n\n"
            "> 目标 / 范围 / 第一期边界 / 技术栈 / 术语 / 路线图。待填。\n"
        ),
    }
    for relpath, content in skeletons.items():
        fpath = os.path.join(project_dir, relpath)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        created.append(relpath)

    return CreateResult(success=True, project_dir=project_dir, created_files=created)
