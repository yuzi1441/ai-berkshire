# 投资决策看板

`tools/build_investment_dashboard.py` 读取报告库，生成：

- `reports/00-index/投资决策总表.md`：Obsidian 个股总表 + 历史研报结论
- `reports/00-index/报告库-MOC.md`：报告库导航
- `data/investment-dashboard/decision_board.json`：当前个股结论
- `data/investment-dashboard/report_history.json`：每家公司的历史研报结论
- `data/investment-dashboard/post_buy_tracking.json`：用户确认买入后才登记的持仓、论文与复核状态
- `data/investment-dashboard/post_buy_alerts.json`：由行情与复核日期生成的预警
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


## 新报告后如何同步网页

本地生成/归档新公司报告后执行：

```powershell
py -3 tools\build_investment_dashboard.py
py -3 tools\market_snapshot.py
```

推送到 GitHub `main` 后，`.github/workflows/investment-dashboard.yml` 会：

1. 自动重建看板数据
2. 刷新 A/H 行情快照（交易时段）
3. 在配置了 Cloudflare Pages 密钥时自动部署网页

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
py -3 -m http.server 8000 --directory site
```

打开 `http://localhost:8000`。

## Cloudflare Pages

| 类型 | 名称 | 值 |
|---|---|---|
| Secret | `CLOUDFLARE_API_TOKEN` | 可部署 Pages 的 Cloudflare token |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 账户 ID |
| Variable | `CLOUDFLARE_PAGES_PROJECT` | Pages 项目名，如 `ai-berkshire-invest` |

自定义域名在 Cloudflare：Workers & Pages -> 项目 -> Custom domains。


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
