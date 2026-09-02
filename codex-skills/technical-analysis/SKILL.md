---
name: technical-analysis
description: "只需提供公司名，即可自动关联项目中最新的基本面主报告和其引用文件，并生成独立、可复核的技术面买点辅助报告。用于技术分析、买点辅助、均线/RSI/ATR/MACD分析或给旧研报补充技术快照；不用于自动交易或修改投资看板。"
---

## Codex adapter note

This skill is generated from `skills/technical-analysis.md` so Claude Code and Codex users share one canonical workflow.

- Treat `$ARGUMENTS` as the user's request in the current Codex thread.
- When the source mentions Claude-only surfaces such as Task, Agent, WebSearch, Bash, Read, or Write, use the closest Codex capability available in this session: subagents when available, web search when needed, shell commands for local tools, and normal file edits for workspace files.
- Use shared project tools from `tools/` in this repository. Prefer running commands from the repository root with paths like `python3 tools/financial_rigor.py ...`; if the current thread starts outside the repo, locate the actual checkout path first instead of assuming a fixed home-directory path.
- Before starting research, run the `date` command to confirm today's date; treat it as the baseline for "latest" data and state the data cutoff date in the report header. Never assume the current date from training data.
- Preserve the research quality rules from `AGENTS.md`: cross-check financial data, use exact arithmetic tools for valuation/math, and clearly label uncertainty and source gaps.

# 技术面辅助分析

对 `$ARGUMENTS` 指定的公司生成独立技术面报告。标准调用仅需：

```text
$technical-analysis 国电南瑞
```

## 执行

1. 运行 `date`，再检查锁定的指标引擎：

   ```bash
   python3 -c "import talib; assert talib.__version__ == '0.7.1'"
   ```

   缺失时运行 `python3 -m pip install -r requirements-technical.txt`；安装失败就停止。
2. 从 `$ARGUMENTS` 提取公司名并运行：

   ```bash
   python3 tools/technical_analysis.py --company "<公司>"
   ```

   工具会按注册表解析唯一代码，按报告正文中的明确截止日选择最新主报告，关联该报告引用且真实存在的项目文件，并把新报告保存到同一公司目录。它会只读提取主报告中明确写出的建仓价格带，并在报告开头依次给出：当前是否存在有效买入候选区、主报告允许价位、技术观察区、两者交集和红黄绿趋势灯。一个公司存在多个上市代码时必须让用户选择，不得猜测。
   默认技术分析请求截止日必须是运行 `date` 得到的今天；基本面主报告的日期只用于关联，绝不能作为技术分析的 `--as-of`。交易时段内必须剔除尚未完成的当日日线，所以指标行情截止日可以是今天之前最近一个完整交易日。
3. 抽检生成结果：

   ```bash
   python3 tools/report_audit.py extract --report "<destination_path>"
   ```

4. 先阅读 `先看结论`，再按需查看 `三盏趋势灯` 和 `指标明细与复核`。技术观察区只是均线与波动形成的观察位置，绝不能称作买入区；只有主报告明确允许的价格带、技术观察区和“关注分批区”状态同时满足，才可称为“有效买入候选区”。
5. 阅读 `数据质量`。少于 200 个交易日、行情过期或跨源价格偏差超过 1% 时，只能交付诊断，不得给出可执行买点。

## 边界

- 基本面决定是否值得买，技术面只辅助首笔与分批节奏。
- 指标只能由 `tools/technical_analysis.py` 通过 TA-Lib 0.7.1 计算，不得心算或凭图判断。
- 不宣称预测准确率；时点规则未经全市场、多周期可复现回测，不给出胜率、准确率或超额收益承诺。不修改原报告，不运行或修改投资看板。

## Company State 执行接口

Dashboard 只读取结构化 `technical_latest.json`，主表只显示三个字段：`trend`（UP / NEUTRAL / DOWN / UNKNOWN）、`position`（NEAR_MEAN / NORMAL / EXTENDED / BROKEN / UNKNOWN）、`execution`（FAVORABLE / NEUTRAL / UNFAVORABLE / UNKNOWN）。底层指标仍可保留在详情中。30 分钟数据只在 Rule Triggered、Drift 完成且 Checklist PASS 或接近 PASS 时生成；日常批处理更新 latest state，不默认新增日期版 Markdown。
- 用户指定日期、代码、基本面报告或 OHLCV CSV 时，以其明确输入覆盖自动解析。

最终回复分别给出技术分析请求截止日、技术指标行情截止日、基本面主报告日期，并给出报告路径、关联文件数量、技术状态、数据置信度、数据警告，确认看板未修改。
