# 轻量投资逻辑复核：新证据工作流

本工作流只为本地 Codex 客户端中的 Luna 准备可审计输入，不运行模型，
不改变生命周期、下一步动作、正式投资逻辑复核、Checklist、持仓或主报告。

## 数据流

1. 从 `company_state.json` 取得当前 A 股 WATCH 的主报告路径与 SHA。
2. 从主报告正文顶部的明确标签解析证据/报告截止日；无法解析时关闭失败。
3. 复用 `main_report_review.py` 和 `sentiment_snapshot.py` 的现有能力获取：
   本地已审计证据、巨潮公告与财报、重要公司新闻。
4. 复用当前 Event Radar 和带来源、日期的非价格规则评估。
5. 仅保留严格晚于 baseline cutoff 的材料，按内容哈希去重，并形成小型
   evidence package。
6. 当前 Codex 客户端明确切换到 Luna 后，独立读取主报告和 evidence package，
   只能输出 `improved / unchanged / weakened / insufficient_evidence`。
7. 经人工复核的结果仍只通过 `tools/light_thesis_signals.py upsert` 写入唯一
   Git authority。

## 本地命令

先只读检查所有合资格主报告是否有可靠 baseline：

```bash
python3 tools/light_thesis_evidence.py audit-baselines
```

为一家公司准备新证据包（会复用现有网络抓取能力，但不会调用模型）：

```bash
python3 tools/light_thesis_evidence.py prepare \
  --ticker 000333.SZ \
  --output /tmp/000333-light-thesis-evidence.json
```

准备后可独立校验包内排序、日期和指纹：

```bash
python3 tools/light_thesis_evidence.py validate \
  --input /tmp/000333-light-thesis-evidence.json
```

离线检查本地已有证据时可使用 `--local-only`。正式批次不得通过外部
`codex exec` worker 批量启动 Luna；应在当前 Codex 客户端会话中明确选择 Luna。

## 指纹语义

`evidence_fingerprint` 只依赖：

- 当前主报告 SHA；
- baseline cutoff；
- 实际进入判断的证据类型、日期、来源身份与内容 SHA。

它不包含准备时间、模型输出或随机值。相同 baseline 和证据必然得到相同指纹；
新证据进入后指纹变化，现有单记录 authority 会安全替换上一轮 pipeline-validation
结果。相同 baseline/证据却产生不同 signal 时，authority 继续关闭失败。
