# 投资决策看板

`tools/build_investment_dashboard.py` 读取报告库，生成：

- `reports/00-index/投资决策总表.md`：Obsidian 个股总表 + 历史研报结论
- `reports/00-index/报告库-MOC.md`：报告库导航
- `data/investment-dashboard/decision_board.json`：当前个股结论
- `data/investment-dashboard/report_history.json`：每家公司的历史研报结论
- `data/investment-dashboard/post_buy_tracking.json`：用户确认买入后才登记的持仓、论文与复核状态
- `data/investment-dashboard/post_buy_alerts.json`：由行情与复核日期生成的预警
- `data/investment-dashboard/opportunity_scans.json`：Flash 的全量机会扫描、当前机会与临近机会分层
- `site/`：静态网页看板

## 范围

只收录**个股**研究。行业、主题、对比、漏斗、筛选类报告保留在 `reports/`，
不会进入网页看板和投资决策总表。

## 选择规则

每个公司只展示一份“当前结论”：按报告正文明确的数据截止日排序，不用文件修改时间。
若最新有效报告没有价格，显示 `价格未给出`，不会沿用旧报告价格。

同时保留该公司全部历史研报结论（`report_history`），按数据截止日从新到旧排列。

## 分层结论（以第八步为准）

网页「分层结论」与 Obsidian 总表优先展示报告 **第八步：最终决策与行动清单** 中的
**激进型 / 稳健型 / 保守型** 分层建议（含动作与价格带）。

- 第七步三情景估值只作辅助，不单独作为买卖结论
- 粗粒度标签（买入 / 分批买入 / 持有 / 观察 / 减仓）由 **稳健型** 空仓视角推导，仅用于筛选排序
- 列表与详情应同时看三种风格，而不是只看单一「观察/持有」
- 若最新报告缺少分层表，会回挂同公司更完整研报中的分层建议用于展示

## 价格与估值展示

网页和总表**不再展示**自动摘要的价格计划 / 三情景列（容易失真）。

以报告 **估值原文原表** 为准：

- 优先摘录「第七步：估值与安全边际 / 财务质量与估值」并向下包含第八步行动清单原表
- 详情默认打开「估值原文」页签；「摘要」页展示激进/稳健/保守分层
- 若最新报告是较薄的 thesis-tracker，估值原文会回挂同公司更完整研报并标注来源

后端仍会解析价格表与分层建议用于排序与看板字段，但不改写报告正文。

## 当前机会筛选：AI 找机会，你决定买不买

顶部「当前机会筛选」不是自动交易或机械买入筛选：每个 A 股由 Flash 阅读主报告、当前行情、技术辅助、情绪和 Checklist，理解“为什么是现在”。

- 全量扫描：仅使用 `deepseek-v4-flash`
- 当前机会：必须回答“为什么是现在”，并至少指出一个已经满足的关键条件
- 临近机会：具体触发器已经接近或部分满足，但仍差一个决定性条件；单独折叠展示
- 不算机会：好公司、热门叙事、值得研究、估值争议、未来可能到价或未来可能出现事件，不能单独进入机会面板
- 人工深度复核：点击按钮后再使用 `deepseek-v4-pro` + `gpt-5.6-luna`
- 最终决定：模型不输出买卖、仓位或目标价；你阅读依据、反证和报告后自行决定
- 推理：所有调用请求供应商支持的最高推理档；产物会记录实际生效档位，若无法启用不会悄悄降为低推理
- 数据体积：完整模型输入保留在 `data/investment-dashboard` 供审计；公开网页只发布精简结果和行情上下文

收盘后全量扫描：

```powershell
py -3 tools\opportunity_review.py scan
py -3 tools\build_investment_dashboard.py
```

单只股票的深度复核使用 `deepseek-v4-pro` + `gpt-5.6-luna`：

```powershell
py -3 tools\opportunity_review.py deep --ticker 000682.SZ
```

线上看板的「启动深度复核」按钮调用受保护接口，结果写入服务器运行目录而不是 Git 工作区。部署时在 `/etc/ai-berkshire/dashboard-review.env` 设置一个随机长令牌：

```ini
DASHBOARD_REVIEW_TOKEN=replace-with-a-long-random-secret
DASHBOARD_DEEP_REVIEW_DAILY_LIMIT=12
```

未配置令牌时，网页仍可正常浏览，但深度复核接口保持关闭，避免公网消耗模型额度。收盘任务使用的 `/etc/ai-berkshire/sentiment.env` 需要保留 `OPENCODE_GO_API_KEY`；如需覆盖默认模型参数，可使用：

首次点击深度复核会在详情内要求输入令牌；令牌只保存到该浏览器会话，输入后才会向服务器发起模型请求。

```ini
OPPORTUNITY_SCAN_FLASH_REASONING_EFFORT=max
OPPORTUNITY_DEEP_V4PRO_REASONING_EFFORT=max
OPPORTUNITY_DEEP_LUNA_REASONING_EFFORT=high
```


## 新报告后如何同步网页

本地生成/归档新公司报告后执行：

```powershell
py -3 tools\build_investment_dashboard.py
py -3 tools\market_snapshot.py
```

推送到 GitHub `main` 后，`.github/workflows/investment-dashboard.yml` 会：

1. 自动重建看板数据
2. 刷新 A/H 行情快照（交易时段）
3. 由 VPS 静态站点服务提供生产网页

因此：新公司研报只要按路由保存到 `reports/<公司>/` 并推送，网页会同步更新。

## 买入后跟踪与预警

“买入前决策”和“买入后跟踪”在网页中分开显示。主报告里的`买入`或`分批买入`不会自动创建持仓，也不会因技术面、股价异动或论文健康度而被自动改写。

只有确认实际买入后，才登记持仓并建立投资论文：

```powershell
py -3 tools\post_buy_tracking.py register `
  --ticker 600406.SH --company 国电南瑞 --market A股 `
  --buy-date 2026-08-01 --cost-basis 24.37 --position-weight 5 `
  --next-review 2026-11-01 --thesis-report reports/国电南瑞/国电南瑞-thesis.md
```

论文检查完成后更新状态；健康度范围为 1-10：

```powershell
py -3 tools\post_buy_tracking.py update 600406.SH `
  --thesis-status healthy --health-score 8 `
  --last-review 2026-08-01 --next-review 2026-11-01 --review-action 持有
```

股价异动分析完成后记录事件。只有明确需要重审论文时才传入 `--review-required`：

```powershell
py -3 tools\post_buy_tracking.py event 600406.SH `
  --change-pct -6.4 --window 1日 --category 情绪 `
  --summary "大盘与行业同步回撤，暂未发现公司特有事件" `
  --no-review-required --report-path reports/国电南瑞/国电南瑞-news-20260801.md
```

日常行情刷新后执行：

```powershell
py -3 tools\post_buy_tracking.py check
py -3 tools\build_investment_dashboard.py
```

默认预警线为单日涨跌幅 `±5%`、复核日前 7 天、复核日到期/逾期。预警只标记“待分析”或“待复核”，不会自动下单、调仓或改变基本面建议。

## 本地预览

```powershell
py -3 tools\build_investment_dashboard.py
py -3 tools\market_snapshot.py --force
py -3 tools\post_buy_tracking.py check
py -3 tools\build_investment_dashboard.py
Copy-Item data\investment-dashboard\quotes\latest.json site\data\quotes\latest.json -Force
py -3 tools\dashboard_server.py --port 8000 --directory site
```

打开 `http://localhost:8000`。

## 买入建议列（现价对照）

网页在「现价」后增加 **买入建议** 列，用实时/快照现价对照第八步分层价格带：

- 现价落入 **保守** 带 → 适合保守买入（同时满足稳健/激进）
- 现价落入 **稳健** 带（高于保守上限）→ 适合稳健买入
- 现价落入 **激进** 带（高于稳健上限）→ 适合激进买入
- 现价高于全部买入上限 → 不适合买入
- 无分层价或无行情 → 无分层价 / 待比价

可按「买入建议」排序。详情摘要页同步展示该判断。

## 网页操作体验

- **自动跳转**：点击表格行打开右侧/底部详情；URL hash 支持 `#ticker=000651.SZ` 或 `#company=格力电器`，可分享直达。
- **键盘**：`/` 聚焦搜索，`j/k` 或方向键切换个股，`Enter` 打开并跳到估值原文，`Esc` 关闭，`o` 打开研报。
- **实时行情**：交易时段优先通过腾讯行情脚本接口刷新 A/H 现价（约 45 秒）；失败时回退 `site/data/quotes/latest.json` 快照。
- **排序**：结论优先级、现价安全边际、当日涨跌、研报截止日、公司名。
