# 05 · 启动指令(给 CodeX)

> 这是代码生成的入口。先读 `AGENTS.md`(代码规则),再按本指令分阶段生成。
> **规格唯一事实源**:`specs/项目管理工具/`;硬契约:`contracts/*.yaml`(冲突以 YAML 为准)。
> **分阶段生成,一阶段一验收**:每阶段测试通过、且我(设计方)审过,才进下一阶段。卡壳/规格有歧义 → 停下提问,不许猜着写。

## 生成顺序(按依赖)

### 阶段 0 · 脚手架
- 按 `01-架构设计.md §3` 建目录结构;生成 `requirements.txt`、`config.example.toml`、`README.md`(启动说明)、各包 `__init__.py`。
- DoD:`uvicorn app.main:app` 能起一个空壳服务(首页返回占位即可)。

### 阶段 1 · common(公共)
- `models.py`(dataclass:Project/Member/Task/QcIssue,字段对齐 `contracts/db_schema.yaml`)。
- `enums.py`(照搬 `contracts/enums.yaml`)。
- `dates.py`(日期解析/格式化/距今天数,口径见 `02 §6`)。
- DoD:dates 工具有单元测试(正常/异常/空)。

### 阶段 2 · storage(存储)
- `schema.sql`(照搬 `contracts/db_schema.yaml`)、`db.py`(初始化建表)、`repository.py`(见 `03-2`)。
- **测试先行**:建表、`upsert_snapshot` 幂等(同键覆盖)、`get_latest_projects` 取最新快照。
- DoD:storage 测试全绿。

### 阶段 3 · ingest(采集解析)— 最关键
- `template_map.py`(照搬 `contracts/excel_template.yaml`)、`parser.py`、`qc.py`、`scanner.py`(见 `02`、`03-1`)。
- **测试先行**(用样例 xlsx + 构造数据):
  - 正确解析 4 区块;
  - 主键取表内业务ID、快照日期取文件名;
  - 脏数据告警(外协/?/一格多名字/必填空/坏日期);
  - 旧格式样例(业务ID=125)能入库并产出 `BIZ_ID_FORMAT` + `ID_FILENAME_MISMATCH`/`FILENAME_FORMAT`;
  - 同业务同日多文件只入一条。
- DoD:ingest 测试全绿,样例目录可完整入库。

### 阶段 4 · analytics(分析)
- `delay.py`、`resource.py`、`dashboard.py`(见 `03-3`,口径照 `contracts/params.yaml`)。
- **测试先行**:
  - 隔离网关:计划交付 06-15 未交付 → 项目延期;"客户验收"未开始且计划结束已过 → 任务延期;
  - 构造同一人两个时间重叠项目投入 30%+80% → 撞车,peak=110;
  - 距交付天数与临近/逾期判定。
- DoD:analytics 测试全绿。

### 阶段 5 · web(展示)
- `routes.py`、`deps.py`、`templates/`(**以 `mockups/overview.html`、`mockups/detail.html` 为视觉雏形**)、`static/`(含 ECharts 甘特)。
- 路由与页面见 `03-4`、`04`。
- DoD:`/` 总览、`/project/{id}` 详情+甘特、`/delay`、`/resource`、`/qc` 均可访问;点"扫描 NAS"能入库刷新;甘特"今天"线正确。

## 通用约束(再次强调)
- 红线见 `AGENTS.md` 第二部分(主键、只读 Excel、锚点解析、脏数据进质检、分析不落库)。
- 每阶段小步 commit,信息写清改了什么。
- 不擅自扩展需求;新点子写进 `路线图.md`。
