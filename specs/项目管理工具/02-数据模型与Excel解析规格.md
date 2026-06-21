# 02 · 数据模型与 Excel 解析规格

> 这是整个工具的地基。解析必须**容错**:模板专人维护、布局相对固定,但仍可能有空列、合并单元格、脏数据。
> 核心策略:**靠"区块锚点 + 标签匹配"定位,不写死行号列号**,以抵抗行/列轻微移动。
>
> **权威源**:本文档的字段映射、枚举、类型规则均有机器可读副本于 `contracts/`(`excel_template.yaml`、`enums.yaml`、`params.yaml`)。**如本 MD 与 contracts 冲突,以 contracts 为准。** MD 讲"为什么/怎么做",YAML 锁"精确是什么"。

## 1. 模板结构(来源:`业务填写表` sheet)

模板按竖向 4 个区块排列,每块有中文标题行作为锚点:

| 区块 | 锚点文字(出现在某行 A 列) | 形态 |
|---|---|---|
| 一、业务基本信息 | `一、业务基本信息` | 键值对(标签-值横向成对) |
| 二、合同与经营信息 | `二、合同与经营信息` | 键值对 |
| 三、人员分工 | `三、人员分工` | 表头 + 多行明细 |
| 四、阶段 / 任务拆解 | `四、阶段` | 表头 + 多行明细 |

> 另有 `字典参考` sheet,仅指向外部数据字典,**解析时忽略**。

## 2. 解析总流程(parser.py)

1. 打开工作簿,取 `业务填写表`(若不存在,取第一个 sheet,并记 qc warning)。`data_only=True` 读计算值。
2. 扫描 A 列,记录 4 个区块锚点所在行号,得到每块的行区间。
3. 基本信息、合同经营:在区块行区间内做**标签匹配键值提取**(见 §4)。
4. 人员分工、阶段任务:定位**表头行**(含关键列名),按列名映射列号,逐行读至"空行或下一锚点"(见 §5)。
5. 同步运行质检规则(见 §7),产出 `QcIssue` 列表。
6. 返回 `Snapshot`(project + members[] + tasks[])与 qc[]。

## 3. 键值提取通用规则

- **标签归一**:取单元格文本,去首尾空格、去 `★`、去全角空格、去末尾 `(元)`/`(员工ID)` 等括注后比较。
- **⚠ 多列网格**:模板一行可能含多对"标签-值",标签分布在 A/C/D/G 等多列,**不只 A 列**。必须逐行扫描所有列找标签,不能只读 A 列。
- **取值**:从标签单元格右侧相邻单元格起、到**本行下一个标签单元格之前**的区间内,取第一个非空值;值为空时不得越过下一个标签取值(否则会把下一对的标签当成值)。
- 找不到标签 → 该字段存 NULL(不报错);标签找到但值空 → NULL(required 字段补 REQUIRED_EMPTY)。
- 每个命中字段都要跑必填检查——漏看标签会连带漏掉必填校验。
- 日期值:见 §6;数字值:见 §6。

## 4. 区块一/二字段映射

### 区块一 · 业务基本信息 → `snapshot` 列

| 标签(归一后) | 目标列 | 类型 | 必填★ | 备注 |
|---|---|---|---|---|
| 业务ID | biz_id | 文本 | ★ | 权威主键来源,校验格式见 §7 |
| 业务类型 | biz_type | 文本 | | |
| 当前阶段 / 状态 | stage_status | 文本 | ★ | 也写作"当前阶段/状态" |
| 业务名称 | project_name | 文本 | ★ | |
| 客户名称 | customer | 文本 | | |
| 客户行业 | customer_industry | 文本 | | |
| 客户联系人 | (不入库 / 可选入 customer 备注) | 文本 | | 第一期不展示,可忽略 |
| 业务描述 / 一句话说明 | description | 文本 | | |
| 关键任务 / 交付内容 | deliverables | 文本 | | |
| 立项日期 | setup_date | 日期 | | |
| 计划交付日期 | plan_deliver_date | 日期 | | 延期判定用 |
| 实际交付日期 | actual_deliver_date | 日期 | | 空=未交付 |
| 完成度% | progress_pct | 数字 | ★ | 0–100 |
| 风险等级 | risk_level | 文本 | | 低风险/中风险/高风险等 |
| 风险描述 / 难点 | risk_desc | 文本 | | |
| 当前主要问题 | current_issue | 文本 | | |

### 区块二 · 合同与经营信息 → `snapshot` 列

| 标签(归一后) | 目标列 | 类型 |
|---|---|---|
| 合同状态 | contract_status | 文本 |
| 合同编号 | contract_no | 文本 |
| 合同金额 | contract_amount | 数字 |
| 已开票金额 | invoiced_amount | 数字 |
| 已回款金额 | received_amount | 数字 |
| 毛利率%估算 | gross_margin_pct | 数字 |
| 项目总负责人 | owner_name | 文本 |
| 项目经理 | pm_name | 文本 |
| 备注 | (可忽略) | 文本 |
| 最后更新日期 | last_update_date | 日期 |
| 表单状态 | form_status | 文本 |

> 样例中合同区多为空,属正常;一律存 NULL,页面显示"—"。

## 5. 区块三/四明细解析

### 区块三 · 人员分工 → `snapshot_member`

表头行特征:同一行内出现 `姓名` 且含 `投入工作量`。按表头列名映射:

| 列名(含) | 目标列 |
|---|---|
| 姓名 | name |
| 员工ID | emp_id |
| 担任角色 / 角色 | role |
| 具体负责任务 | task_desc |
| 参与开始 | join_start(日期) |
| 参与结束 | join_end(日期) |
| 投入工作量% | workload_pct(数字) |
| 当前完成情况 | progress_note |
| 上级评价 | eval |
| 备注 | note |

读取规则:
- 从表头下一行起,逐行读取,`row_idx` 用原表行号。
- **终止条件**:遇到整行全空,或遇到下一区块锚点(`四、阶段`),停止。
- `is_external` 判定:`name` 经 strip 后 ∈ {`外协`,`?`,`？`,`""`/None} → `is_external=1`;否则 0。`is_external=1` 的行**不参与资源撞车计算**。
- 一格多名字(`name` 含换行/`、`/`,`/`/`):按真实人员处理为**多人**?——第一期**不拆**人员行(人员区一般一人一行);若 `name` 含分隔符 → 保留原值 + 记 qc warning(`MULTI_NAME_IN_MEMBER`)。

### 区块四 · 阶段/任务拆解 → `snapshot_task`

表头行特征:同一行内出现 `#` 且含 `计划开始`(或含 `阶段/任务名称`)。映射:

| 列名(含) | 目标列 |
|---|---|
| # | seq(文本,允许重复) |
| 阶段/任务名称 / 任务名称 | task_name |
| 负责人 | owner |
| 计划开始 | plan_start(日期) |
| 计划结束 | plan_end(日期) |
| 实际开始 | actual_start(日期) |
| 完成度% | progress_pct(数字) |
| 状态 | status |
| 备注 | note |

读取规则:
- 从表头下一行读至整行全空或文件结束。
- **跳过空壳行**:`task_name` 为空的行不入库(样例尾部 35/36/37 等空行)。
- `owner` 可能是 `外协` 或多名字 → 原样存(任务负责人不做人员冲突计算,不影响撞车)。
- `status` 原样存;甘特图按 §8 颜色口径映射。

## 6. 类型转换规则

- **日期**:
  - openpyxl 读出 `datetime` → 取 `date`,格式化 `YYYY-MM-DD`。
  - 读出字符串(如 `2026-04-16` 或 `2026/4/16`)→ 尽力解析为日期;解析失败 → 存原文本到对应字段?不,日期字段解析失败存 NULL + qc warning(`BAD_DATE`)。
  - 空 → NULL。
- **数字(百分比/金额)**:
  - 数值型直接取 `float`。
  - 字符串 `65%` / `65 %` → 去 `%`/空格转 `float`。
  - 含非数字(如 `约65`)→ NULL + qc warning(`BAD_NUMBER`)。
  - 空 → NULL。
- **文本**:strip 首尾空白;空串视为 NULL。

## 7. 质检规则(qc.py)→ `qc_issue`

`severity ∈ {error, warning}`。error 不阻断其他文件,但该文件可能数据不可用。

| issue_type | severity | 触发条件 | location 示例 |
|---|---|---|---|
| FILE_OPEN_FAIL | error | 文件打不开/非法 xlsx | 文件级 |
| SHEET_MISSING | warning | 无 `业务填写表`,回退首个 sheet | 文件级 |
| BIZ_ID_MISSING | error | 表内业务ID 为空 | 区块一/业务ID |
| BIZ_ID_FORMAT | warning | 业务ID 不匹配 `^RW\d{4}-\d{3}$` | 区块一/业务ID |
| ID_FILENAME_MISMATCH | warning | 表内业务ID ≠ 文件名解析出的业务ID | 文件名 vs 单元格 |
| REQUIRED_EMPTY | warning | ★必填字段为空(业务名称/阶段状态/完成度等) | 对应字段 |
| BAD_DATE | warning | 日期字段无法解析 | 对应字段 |
| BAD_NUMBER | warning | 数字字段无法解析 | 对应字段 |
| MEMBER_EXTERNAL | warning | 人员姓名为 外协/?/空(已置 is_external) | 人员区某行 |
| MULTI_NAME_IN_MEMBER | warning | 人员姓名一格多名字 | 人员区某行 |
| WORKLOAD_MISSING | warning | 人员 workload_pct 为空(撞车分析缺数据) | 人员区某行 |
| DUP_SNAPSHOT_FILE | warning | 同业务ID+同快照日期出现多文件 | 文件级 |
| FILENAME_FORMAT | warning | 文件名不符合 `{ID}-{名称}【YYYYMMDD】.xlsx` | 文件名 |

主键与日期口径(再次明确,全系统唯一标准):
- **主键 biz_id = 表内"业务ID"单元格值**(权威)。
- **快照日期 = 文件名【YYYYMMDD】**;文件名无法解析出日期 → 该文件记 `FILENAME_FORMAT` warning,回退用文件修改日期(mtime)的日期,并在 message 注明。
- 表内ID 与文件名ID 不一致 → 以表内为准 + `ID_FILENAME_MISMATCH` warning。

## 8. 状态 → 甘特颜色口径(供 04 页面引用)

| 任务 status(归一,含义匹配) | 颜色语义 | 备注 |
|---|---|---|
| 已完成 / 完成 / 100% | 绿(已完成) | 或 progress_pct=100 |
| 进行中 / 部分完成 | 黄(进行中) | 或 0<progress_pct<100 |
| 未开始 / 空 | 灰(未开始) | 或 progress_pct 为空/0 且无实际开始 |

> 当 status 与 progress_pct 矛盾(如 status=未开始但 progress=100)→ 以 status 文本优先,记 qc warning 可选(第一期可不强制)。

## 9. dataclass(common/models.py 约定)

```python
@dataclass
class Project:        # 对应 snapshot 主表字段
    biz_id: str
    snap_date: str
    project_name: str | None
    # ... 其余字段同 snapshot 表列
    members: list["Member"]
    tasks: list["Task"]

@dataclass
class Member:         # 对应 snapshot_member
    row_idx: int
    name: str | None
    emp_id: str | None
    role: str | None
    join_start: str | None
    join_end: str | None
    workload_pct: float | None
    is_external: bool
    # ...

@dataclass
class Task:           # 对应 snapshot_task
    row_idx: int
    seq: str | None
    task_name: str | None
    owner: str | None
    plan_start: str | None
    plan_end: str | None
    actual_start: str | None
    progress_pct: float | None
    status: str | None
    note: str | None

@dataclass
class QcIssue:
    biz_id: str | None
    snap_date: str | None
    source_filename: str
    severity: str        # error / warning
    issue_type: str
    location: str
    message: str
```
