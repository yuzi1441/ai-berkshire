---
name: thesis-drift
description: "AI Berkshire skill: 投资论文漂移检测：分清事实变化与措辞变化. Source: skills/thesis-drift.md."
---

## Codex adapter note

This skill is generated from `skills/thesis-drift.md` so Claude Code and Codex users share one canonical workflow.

- Treat `$ARGUMENTS` as the user's request in the current Codex thread.
- When the source mentions Claude-only surfaces such as Task, Agent, WebSearch, Bash, Read, or Write, use the closest Codex capability available in this session: subagents when available, web search when needed, shell commands for local tools, and normal file edits for workspace files.
- Use shared project tools from `tools/` in this repository. Prefer running commands from the repository root with paths like `python3 tools/financial_rigor.py ...`; if the current thread starts outside the repo, locate the actual checkout path first instead of assuming a fixed home-directory path.
- Before starting research, run the `date` command to confirm today's date; treat it as the baseline for "latest" data and state the data cutoff date in the report header. Never assume the current date from training data.
- Preserve the research quality rules from `AGENTS.md`: cross-check financial data, use exact arithmetic tools for valuation/math, and clearly label uncertainty and source gaps.

# 投资论文漂移检测：分清事实变化与措辞变化

对 $ARGUMENTS 执行投资论文漂移检测。

**支持输入格式**：
- `公司名 旧报告路径 新报告路径` — 指定两份研究报告或论文快照进行对比
- `公司名 reports/{公司名}-thesis-旧日期.md reports/{公司名}-thesis-新日期.md` — 对比两份带日期的论文快照
- `公司名` — 默认进入看板生命周期漂移模式：先读取 `decision_board.json`、`thesis_drift.json`、`watch_tracking.json` 和 `post_buy_tracking.json`，以基线和最新事实做增量检查；如果没有基线则转入缺失基线处理

> "当事实改变时，我就改变想法。你呢？" —— 凯恩斯
>
> "股价波动不是论文漂移，事实变了才是。" —— AI Berkshire

## 设计理念

长期持仓最难的不是每天读新闻，而是区分三件事：
- **事实改变**：收入、利润率、竞争格局、管理层行为、资本配置发生可验证变化
- **价格改变**：市场情绪或估值倍数变化，但生意本身未变
- **措辞改变**：两份报告表达不同，但底层证据和判断没有变化

投资论文漂移检测的目标是：**只在证据变化时承认论文变化**。不能因为报告换了写法就制造漂移，也不能因为股价涨跌就误判基本面。

本 Skill 依赖 `/thesis-tracker` 输出的结构化维度：核心假设清单、红线清单、估值锚点、追踪记录表。看板中的 `post_buy_tracking` 是持仓真相源；`WATCH/PRE_BUY` 不得创建买入论文。没有结构化基线时，先标注缺失，不得把最新主报告直接伪装成历史基线。

## 执行流程

### 第一步：判断操作模式

解析 `$ARGUMENTS`：
- 如果只提供公司名且看板能找到标的 → 默认进入**生命周期模式**，先分流 WATCH/PRE_BUY 或 HOLDING
- 如果提供两份报告路径 → 进入**手动指定报告对比**模式
- 如果只提供公司名但找不到结构化基线 → 进入**缺失基线处理**模式
- 如果两份报告不是同一家公司 → 停止并要求用户确认，不做跨公司漂移判断

## 模式0：生命周期漂移（默认路径）

### 0A：识别生命周期

按以下优先级解析当前状态：

1. `post_buy_tracking.positions[ticker]` 中 `status=holding/paused` → `HOLDING`
2. `status=closed` 或显式退出记录 → `EXITED`
3. `lifecycle.json` 的显式记录 → `WATCH` 或 `PRE_BUY`
4. 没有实际买入确认 → 默认 `WATCH`

主报告写着“买入/分批买入”不能创建持仓，也不能跳过 Checklist。`WATCH` 与 `PRE_BUY` 只允许 `KEEP WATCH / RUN CHECKLIST / DROP`。

### 0B：WATCH/PRE_BUY MODE

读取 `watch_tracking.json` 的轻量记录和当前 canonical main report，只关注买入条件、放弃条件、估值/价格锚点与最新事实。不得写入买入论文，不得输出 `ADD/HOLD/REDUCE/EXIT`。

固定输出：

```json
{
  "mode": "watch",
  "lifecycle": "WATCH",
  "drift_direction": "improved|unchanged|weakened",
  "severity": "none|minor|major",
  "action": "keep_watch|run_checklist|drop",
  "buy_conditions_met": 0,
  "buy_conditions_total": 0,
  "patch_required": false,
  "affected_sections": [],
  "last_checked": "YYYY-MM-DD",
  "next_review": "YYYY-MM-DD"
}
```

判定规则：没有新事实就是 `unchanged + none + keep_watch`；只有价格/估值变化时更新看板或建议复跑 Checklist，不改写主报告；买入条件全部满足才输出 `run_checklist`；重大负面事实或红线触发才输出 `drop`。minor/major 基本面变化要列出受影响的主报告章节，但只有确有必要时才 patch canonical report，不新建一篇完整报告。

### 0C：HOLDING MODE

持仓基线只来自原始买入论文和 `post_buy_tracking`，固定检查五个维度：`valuation_anchor`、`core_assumptions`、`red_lines`、`management`、`moat`。价格跌涨本身不能判定论文破裂。

固定输出动作只有 `ADD / HOLD / REDUCE / EXIT`：红线或核心假设破裂 → `EXIT`；重大弱化/论文受损 → `REDUCE`；健康且新增加仓条件已验证 → `ADD`；其余 → `HOLD`。输出后必须保留并更新原有持仓字段、健康度、指标、复核日期和事件记录，不能另建一套持仓真相源。

### 0D：增量更新与历史上限

每次运行只记录本次新事实和五维变化。`data/investment-dashboard/thesis_drift.json` 中每个标的的 `history` 最多保留 12 条；无变化时不修改 canonical main report。结构化结果至少包含 `status`、`direction`、`severity`、`action`、`patch_required`、`affected_sections`、`last_checked`、`next_review` 和证据摘要。

### 0E：主报告修改门槛

- `none`：不改主报告。
- 只有价格/估值：更新看板，必要时 `RUN CHECKLIST`，不重写主报告。
- `minor` 基本面变化：只 patch 受影响章节，并保留原文历史。
- `major` 基本面变化：先做深度复核，再 patch canonical main report；不得让旧报告继续充当当前主报告。
- 每家公司只能有一个 canonical main report；旧报告进入 `report_history`，不是第二个当前决策。

该模式的最终报告必须同时列出：当前生命周期、漂移方向/严重度、五维证据对照、动作、是否需要 patch、下次复核日期，以及“技术面/情绪面仅辅助”的说明。

---

## 兼容模式A：指定报告对比

### A1：读取并校验两份报告

读取旧报告和新报告，提取：
- 报告日期、公司名、股票代码
- 核心论文（5句话）
- 核心假设清单
- 红线清单
- 估值锚点
- 追踪记录表
- 管理层质量判断
- 竞争护城河判断
- 当前建议动作（买入 / 持有 / 观察 / 减仓 / 清仓）

如果报告缺少关键结构，先标注"结构缺失"，但仍尽量从正文中抽取证据；抽取不到的维度标为"无法判断"，不能编造结论。

### A2：证据归一化

把两份报告中的事实证据整理成同一张表：

| 维度 | 旧报告证据 | 新报告证据 | 数据来源 | 是否可验证 |
|------|-----------|-----------|---------|-----------|
| 估值锚点 | | | | |
| 核心假设 | | | | |
| 红线 | | | | |
| 管理层质量 | | | | |
| 竞争护城河 | | | | |

**只比较证据，不比较文风。** 如果新旧报告只是同义改写、排序变化、语气变化，但事实数据和判断阈值没有变化，判定为 Unchanged。

### A3：数值与估值校验

所有数值变化必须使用 `tools/financial_rigor.py` 做精确计算，禁止 LLM 心算：

```bash
python3 tools/financial_rigor.py verify-valuation \
  --price {当前价格} \
  --eps {EPS} \
  --bvps {每股净资产} \
  --fcf-per-share {每股自由现金流}
```

如需计算市值、百分比变化、目标价差异或情景估值，使用：

```bash
python3 tools/financial_rigor.py verify-market-cap --price {价格} --shares {股本} --reported {报告市值} --currency {币种}
python3 tools/financial_rigor.py cross-validate --field {字段} --values '{JSON}' --unit {单位}
python3 tools/financial_rigor.py three-scenario --price {价格} --eps {EPS} --shares {股本亿} --growth {乐观} {中性} {悲观} --pe {乐观PE} {中性PE} {悲观PE}
python3 tools/financial_rigor.py calc --expr '{精确算式}'
```

关键财务数据必须至少两处独立来源交叉验证。来源不足、口径不一致、无法复核的数字必须标注为"低置信度 / 待核实"。

### A4：逐维度判定漂移

固定使用以下维度，不要临时增减：

| 维度 | 判定重点 | Improved | Unchanged | Weakened |
|------|---------|----------|-----------|----------|
| 估值锚点 | 内在价值、PE/PB/FCF Yield、安全边际、目标价区间 | 安全边际扩大或内在价值上修且经工具验算 | 估值区间和安全边际无实质变化 | 安全边际收窄、内在价值下修或估值假设失效 |
| 核心假设清单 | 收入增速、利润率、现金流、用户/订单/产能等可验证假设 | 更多假设被新证据强化 | 假设状态与证据基本一致 | 假设边际弱化、受损或破裂 |
| 红线清单 | 诚信、监管、业务衰退、竞争突破、管理层异常动作 | 原有红线风险解除或显著下降 | 未触发且风险水平不变 | 红线被触发或触发概率上升 |
| 管理层质量 | 诚信、资本配置、回购分红、执行力、股东友好度 | 新行为提高信任度 | 行为延续旧判断 | 行为损害信任或资本配置变差 |
| 竞争护城河 | 市占率、定价权、网络效应、成本优势、替代威胁 | 护城河变宽或竞争优势被验证 | 格局无实质变化 | 护城河被削弱或竞对突破 |

每个维度只能给出三类结论：**Improved / Unchanged / Weakened**。

### A5：证据驱动规则

每个非 Unchanged 的结论必须引用导致变化的具体新证据：
- 财报行项目：例如收入增速、毛利率、经营现金流、回购金额、净现金
- 监管披露：例如 10-K/20-F、年报、中报、港交所公告、SEC filing
- 新闻事件：例如管理层变动、监管处罚、重大客户流失、竞品突破
- 价格与估值：必须说明这是"估值变化"还是"基本面变化"，不能混淆

如果找不到能解释变化的证据，必须判定为 **Unchanged** 或 **无法判断**，不能用措辞差异推断漂移。

### A6：输出漂移报告

#### 报告结构

```
一、对比对象与时间跨度
二、总体结论：论文是否漂移
三、维度漂移表
四、证据差异明细
五、估值与数值验算
六、建议动作迁移
七、不确定项与需补充来源
八、下次跟踪重点
```

#### 维度漂移表

| 维度 | 旧判断 | 新判断 | 漂移方向 | 触发证据 | 置信度 |
|------|-------|-------|:--------:|---------|:------:|
| 估值锚点 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 核心假设清单 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 红线清单 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 管理层质量 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 竞争护城河 | | | Improved / Unchanged / Weakened | | 高/中/低 |

**Unchanged 行的触发证据写 `—`，不要为了填表编造证据。**

#### 总体结论必须回答

1. **论文是否漂移？** 未漂移 / 正向漂移 / 负向漂移 / 证据不足无法判断
2. **漂移来自哪里？** 估值 / 基本面 / 管理层 / 竞争格局 / 红线事件
3. **是事实变化还是价格变化？** 明确拆开说明
4. **建议动作如何迁移？** 例如：Watch → Buy、Buy → Hold、Hold → Reduce、Reduce → Exit
5. **下一步需要什么证据？** 下一份财报 / 监管披露 / 管理层说明 / 竞对数据

---

## 兼容模式B：自动快照对比

### B1：查找快照

在 `reports/` 中查找：
- `reports/{公司名}-thesis.md`
- `reports/{公司名}-thesis-*.md`
- `reports/{公司名}/` 目录下包含 `thesis`、`论文`、`追踪` 的报告

选择时间最早且结构完整的文件作为旧报告，时间最新的文件作为新报告。若用户指定日期，以用户指定为准。

### B2：防止错误配对

对比前必须确认：
- 公司名或股票代码一致
- 报告日期不同
- 两份报告都包含可抽取的论文结构或研究结论

如果无法确认同一公司，停止并要求用户提供明确路径。

### B3：执行模式A

找到两份有效快照后，按模式A完整执行。

---

## 模式C：缺失基线处理

如果只找到一份报告或没有找到旧快照：

1. 明确说明：**缺少可比较的历史基线，不能执行漂移检测**
2. 不要根据记忆或市场印象补造旧论文
3. 引导用户先使用 `/thesis-tracker {公司名} 建立论文` 建立结构化基线
4. 如果当前报告已足够完整，可建议将它保存为 `reports/{公司名}-thesis.md` 作为未来漂移检测基线

输出格式：

```
无法执行论文漂移检测：缺少历史基线。

已找到：
- 当前报告：{路径 / 未找到}
- 历史基线：未找到

建议：
1. 先运行 /thesis-tracker {公司名} 建立论文
2. 下次有新财报或重大事件后，再运行 /thesis-drift {公司名} 旧报告 新报告
```

---

## 关键原则

- **证据优先于措辞** — 同义改写不是漂移，只有事实证据变化才是漂移
- **基本面优先于股价** — 股价涨跌只影响估值锚点，不自动改变生意质量
- **数值必须验算** — 所有百分比、估值倍数、目标价差异必须用 `tools/financial_rigor.py`
- **不确定就标注不确定** — 来源缺失、口径不一致、无法复核时，不要硬判
- **红线单独处理** — 红线触发优先级高于估值便宜，不能被低 PE 掩盖
- **输出必须可复盘** — 每个 Improved / Weakened 结论都要能追溯到具体证据
- **生命周期先于报告措辞** — 看板先回答“现在处于观察、买入前、持仓还是退出”，报告结论只是证据层
- **默认增量，不默认重写** — `thesis-drift 公司名` 不把新报告和旧报告全文机械比较，也不因为措辞变化生成新主报告
- **动作必须受状态约束** — 未实际买入不能出现持仓动作；已持仓不能退回观察池掩盖卖出判断

## Decision Rules 联动

看板在主报告与生命周期之间增加持久化的 Decision Rules 层。规则只记录
“什么情况下值得重新做决策”，不替代投资论文，也不直接生成 BUY/SELL。

首次迁移使用 `python3 tools/extract_decision_rules.py --dry-run` 预览；确认后才使用
`--write` 保存到 `data/investment-dashboard/decision_rules.json`。每条规则必须保留
`source_report`、`source_section`、`source_text`、`created_at`、`updated_at`，抽取不明确的
条件标记 `confidence=low` / `needs_review=true`，并关闭自动判断。

规则状态与漂移的衔接如下：

```text
主报告 → 首次规则抽取 → WATCH
价格规则 → 新鲜同市场行情自动评估
指标/事件规则 → 财报、事件或 thesis-drift 复核
规则接近/触发 → RUN CHECKLIST 或 Thesis Review
用户确认成交 → Buy Thesis → HOLDING Drift
```

价格规则必须绑定具体 `ticker`、`market`、`currency`；基本面规则可以使用共同的
`company_id`。漂移变弱时，看板只将相关条件规则标为 `needs_review`，不会自动调仓；
`HOLDING` 的最终动作仍由原始买入论文和用户确认的跟踪结果决定。
