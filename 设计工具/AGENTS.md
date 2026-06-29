# AGENTS.md — 协作约定与项目记忆

> 本文件是 Codex 在本项目的长期指令与记忆。每个会话开始都应遵循。

---

## 一、思考方式(每次都照做,最重要)

对任何**修复**或**设计**请求,默认按这三步给方案,不用用户提醒:

1. **先复述底层目标和用户**(一句话):这功能/这次改动是为谁、解决什么问题。先从"补丁视角"跳到"设计视角"。
2. **给两种方案**:一个**最小改动**(低风险补丁)+ 一个**更优设计**(可能重构),各列利弊与代价。不要默认只给最小补丁。
3. **指出能不能一改多得**(举一反三):这个改动会不会同时影响/顺带解决 安全、UX、性能、数据模型、其它模块?把多个镜头**叠起来看**,不要切开(典型教训:文档模块"修安全洞"其实就是"重做上传体验"的机会,当初切开看了,漏了)。

补充准则:
- **敢质疑前提**:不要默认接受现有设计的形状;必要时问"这功能本身该不该是这个形态"。
- **先确认优化目标**:同一问题,"要最小风险" vs "要最干净设计"给的方案不同;不确定就先问用户一句。
- **改代码前尽量自测**(沙盒无 flask,可验证纯逻辑、SQL、路径安全、docx 渲染等),改完给重启/刷新步骤。

---

## 二、项目背景

- **富成智能项目管理系统 / ProjectHub**:硬件板卡研制企业的项目管理体系软件。
- 技术栈:后端 Flask + SQLite(`ProjectHub/backend`),前端 Vue3 + Vite + Pinia(`ProjectHub/frontend`),图表 Chart.js,文档 openpyxl / python-docx / docxtpl。
- 8 个模块:制度检索(policy)、报表看板(dashboard)、需求管理、项目管理、资源管理、售后管理(含问题分析)、文档管理。
- 业务依据是体系文件 **QFD-GL13 系列**(`体系文件PDF/`、`硬件板卡项目管理体系_QFD-GL13_V1.0/`),设计要贴着这些规定走,别凭空造概念。

---

## 三、已确立的架构原则(不要走偏)

- **单一事实来源**:每种数据只有一个"家"。项目分配数据 → 项目 Excel;资源主数据/售后工单/文档 → 软件内;别把同一数据塞两处。
- **Excel = 交换格式**:导入(Excel→DB)/ 导出(DB→Excel)/ 回写互为逆操作,版式一致;用"母版填充法"保版式。
- **只读聚合层**:看板 / 资源 / 售后问题分析,都是跨模块**只读聚合**,复用各模块已有 `/stats`,**不反写、不重算、不拥有别人的表**。
- **模块边界**:每个模块明确"拥有(读写)/ 只读 / 不碰"。
- **计划管理不做 CPM 排程**:日期由 Excel/手工直接录;CPM 代码冻结保留、不接 UI。

---

## 四、踩过的坑(别重犯)

- **docxtpl 0.20.x 的 `{%tr%}` 表格行循环有 bug**(开标签被吞、报 endfor)→ 动态表格(如归档清单)用 **python-docx 克隆模板行**;只有标量+复选框的(售后记录单)用 docxtpl 没问题。requirements 锁 docxtpl==0.19.1。
- **母版占位符**别被 Word 自动更正/拆成多个 run,否则识别不出。
- **后端 `debug=False` 不热加载**:改后端必须**重启**(`lsof -ti :5001 | xargs kill -9` 再 `python -m backend.app`)。
- **前端是后端发 dist 成品**:改前端要么 `npm run build` 重打包(走 :5001),要么开 `npm run dev`(:3000,自动热更新)。改了没生效先想是不是跑的旧产物。
- **启动方式**:从 `ProjectHub/` 目录用 `python -m backend.app` 或 `python start.py`,别直接对 `backend/app.py` 点运行(已加 sys.path 引导兜底)。

---

## 五、已知待修(详见 `ProjectHub_代码审查报告_v2`)

- **P0 文档上传**:已设计"清单驱动 + 真实文件上传"简化方案(`文档归档上传_简化重设计_编码提示词.html`),落地后顺带修掉**任意文件读取**漏洞。
- 全站**无鉴权**;约 131 处 `str(e)` 外泄;无上传大小限制;前端 121 处 fetch 仅 1 处查 `res.ok`;连接每查询新建。
- 已修复别再动:requirements 表的 `CREATE IF NOT EXISTS`、会议附件 `secure_filename`+realpath、已参数化 SQL、冻结的 CPM、看板网格布局与优雅降级。

---

## 5.5、执行铁律

- **找不到规格文件就停**：如果执行命令中引用的规格文件（如 `_梳理/R6-batch-*.md`）在本地找不到，**立即停下并提示用户**，不要猜测内容、不要自行编造替代方案。规格文件是设计方（Claude）产出的行为契约，缺失时无法保证执行正确性。
- 规格文件默认存放在 `_梳理/` 目录下。

---

## 六、产出习惯

- 设计/编码提示词统一用**蓝色卡片 HTML 风格**(现状→目标→改法 + 末尾"可复制总提示词"带复制按钮),放在项目根目录。
- 母版文件(Excel/docx)放 `ProjectHub/backend/files/template/`;预置数据(如归档清单)放 `ProjectHub/backend/files/`。
- 给方案时标"必需/视情况",空数据要有占位,别留大白板。

### 前端样式:fc-* 设计系统迁移约定

- **优先复用 `src/styles/global.css` 的 `.fc-*` 通用类**(`fc-page/toolbar/card/btn/field/form-row/input/select/search/filter/chip/tag/table/empty/toast/modal`),页面 scoped 样式只留"本页特例布局",别各自重造按钮/表格/输入框/toast。
- **颜色一律走令牌** `var(--color-*)`(见 `themes.css`),禁止新增硬编码十六进制色;确无对应令牌的语义强调色(如统计卡浅底、个别状态紫)才保留字面值并注释说明。
- **跨页重复的样式抽到 global**:严重等级用全局 `.fc-sev-致命/严重/一般`(纯文字着色,售后两页已共用);**状态色按页配置**——列表内作彩色文字、详情/卡片头作 `.fc-tag` 药丸,形态不同就各页留 `.st-*` 配色,不强行合并造成视觉改变。
- **两列信息网格 `.info-grid` 属页面特例布局**,保留为薄局部类;内部字段仍用 `.fc-field`。卡片(`.section`)用 `display:flex;flex-direction:column;gap` 统一子项间距,别在各元素上散落 margin。
- 迁移完成度自检三项:**框架**(page/toolbar/card/btn)、**表单**(field/form-row/input)、**布局**(网格间距/令牌化)。范本见已完成的 `aftersale/TicketForm.vue`、`index.vue`、`TicketDetail.vue`。
- 改完提示:纯前端走 `npm run dev`(:3000 热更)或 `npm run build`(:5001 重打包),后端无需重启。

---

#dels.py` 因补丁操作导致缩进损坏 → 从 `git show HEAD` 恢复干净版本
- 已确认所有 backend `.py` 通过 `py_compile` 编译

### 当前数据库状态

```
after_sales_tickets    15
customers               8
lessons                 5
problem_tags           32
project_actions        21
project_calendars      11
project_changes         5
project_costs          16
project_documents      16
document_versions      23
project_issues         10  (待处理:7, 处理中:1, 已关闭:2)
project_meetings       10
project_members       108
project_risks          22
project_tasks         226
project_workitems      30
projects               14
requirement_followups  10
requirement_logs       15
requirement_members    12
requirement_tasks      16
requirements            5
resources              13
数据库总记录 796
```

### 关键文件变更清单

| 文件 | 变更 |
|---|---|
| `backend/modules/dashboard/routes.py` | `_get_alerts` 逾期改用 computed_statuses；`_get_kpis` executing 只统计执行中 |
| `backend/modules/project/routes.py` | 新增 `/issues` 端点；`handle_issues` 创建时默认 status='待处理' |
| `frontend/src/views/dashboard/index.vue` | 预警条"本月交付"改文案/数据源/下钻；待处理问题/高风险下钻到 `/project/issues` |
| `frontend/src/views/project/IssuesOverview.vue` | **新建** — 跨项目问题总览页 |
| `frontend/src/views/project/components/IssueTab.vue` | 表单新增状态下拉框 |
| `frontend/src/router/index.js` | 注册 `/project/issues` 路由（在 `/project` 之前）；修复 `isActive` 精确匹配 |
| `frontend/src/components/Sidebar.vue` | 新增 `⚠️ 待处理问题` 入口 |


