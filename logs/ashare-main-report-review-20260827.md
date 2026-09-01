# A 股主报告看板分析 — 收尾报告（2026-08-27）

## 背景

GLM 于 2026-08-27 对决策看板 A 股主报告做了全文复核，并在 `logs/` 留下 5 个审查脚本
（`review_dump_board.py`、`review_ashare_worklist.py`、`review_suspects.py`、
`review_stances_check.py`、`review_dump_stances.py`），把 40+ 条修正写进了
`data/investment-dashboard/overrides.json`。但看板最后一次重建发生在 17:10:55，
早于覆盖定稿（脚本时间戳到 17:33），**修正从未被应用**——这就是未收尾的部分。

## 本次完成的工作

1. 重跑全部 5 个审查脚本，复原工作清单：当时看板共 233 条决策，其中 A 股 76 家、
   历史报告 314 份；疑点脚本标记 81 条可疑记录（含正则误报，如 chunfeng-dongli）。
2. 重建看板 `py -3 tools/build_investment_dashboard.py`，逐条矩阵验证覆盖生效：
   - 14 项 action 修正全部生效（一拖股份/江波龙/宇视科技 → 观察；平安集团/格力电器/
     汾酒/泸州老窖 → 分批买入；厦门钨业/特变电工/迈瑞医疗/华明装备/恒瑞医疗/中国神华 → 观察）。
   - buy_price 修正全部生效（CMOC 3-5 元 → 15-17 元；DapuStor 705 元 → 80-120 元；
     深南电路 3 元 → 250-300 元再评估区；生益科技 3 元 → 90-110 元；中国神华清空等）。
   - 散户乙（entity_kind: figure）、小红书（entity_kind: event）按规则移出决策板；
     智元机器人改为 market=未识别、ticker 清空。
3. 修复两处覆盖系统管不到的选择层问题：
   - **东方电缆**：构建器排序选中了较旧的《东方电缆研究报告-20260724》（持有），
     而 GLM 复核的是更新的《东方电缆-research-20260726》（观察，等 2026-08-05 中报）。
     在 `overrides.json` 的 `companies` 段新增东方电缆条目，把主报告、action、
     buy_price、recommendation 指向复核过的 0726 报告。
   - **长江电力重复实体**：`Yangtze-Power`（6 月旧报告 6 份）与 `长江电力`
     （7 月报告 16 份）在板上并列两条。在 `data/report-routing/company_registry.json`
     新增长江电力条目（含别名 "Yangtze Power"/"Yangtze-Power"），合并为单条记录，
     主报告为最新的 `长江电力-thesis.md`（数据截止 2026-07-10），历史合计 22 份。
4. 重建后复验：决策总数 233 → 230；A 股 76 → 72 家；
   `report_routing.py resolve` 对长江电力仍正常解析到 `reports/长江电力`。

## 收尾后的 A 股看板状态

- 72 家：观察 62、分批买入 10（GLM 的口径：论文文件未确认实际持仓时，
  action 跟随"空仓者"立场，故原"持有/减仓"类标签统一改为观察）。
- 27/72 带三档投资人立场（其余报告为"空仓者"单一结论格式，非提取失败）。

## 遗留事项（本次不处理，供后续决策）

| 事项 | 说明 |
| --- | --- |
| 智元机器人仍为 `未提取` | 未上市公司，GLM 已清空 ticker/market；是否也标 entity_kind 移出看板待定 |
| 9 份 A 股报告无数据截止日 | CMOC、DapuStor、Goldwind、Jereh、一拖股份、中创智领、宇视科技、平安集团、神火股份（多为 4-6 月旧报告） |
| 宇视科技无买点 | 结论为"回避"，报告本身未给价格，属正常 |
| 港股/美股召回池疑点 | `review_suspects.py` 另标记约 60 条（章节文件当主报告、被排除目录入选、重复实体等），超出本次 A 股范围 |

## 变更文件

- `data/investment-dashboard/overrides.json`（新增 companies.东方电缆）
- `data/report-routing/company_registry.json`（新增长江电力别名条目）
- 重建产物：`data/investment-dashboard/*.json`、`site/data/*`、`reports/00-index/*`
