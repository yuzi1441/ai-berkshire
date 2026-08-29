# 基本面复核雷达：Windows 端双轮对照与协议修订工作报告

> 本报告仅用于学习与研究，不构成投资建议。
> 作者：ZCode（GLM，Windows 端）；工作日期：2026-08-29；分支：`codex/dongfang-fundamental-review-pilot`（基于 92b2ba10）。
> 阅读对象：Mac 端（`fundamental-review-full` 批量复核的作者设备）。

---

## TL;DR（5 条）

1. **在 Windows 端独立复现并扩展了复核流水线**：以"不读取人工锁定规则"为前提，由 12 组子代理从 93 只股票各自的主报告推导独立规则包（zcode_inline_v1），完成 279 条任务的证据复核，全部输出经程序化校验（结构、枚举、证据归属、引文逐字比对）。
2. **与 Mac 端 deepseek-v4-flash 锁定规则轮逐股对照**：状态一致率 101/279（36%）。分歧主因不是事实冲突，而是**验证纪律宽严差**——deepseek 轮大量用主报告基线数据充当"verified"（126 条 verified vs 我方 6 条）。
3. **协议漏洞已修复**：`tools/fundamental_review_radar.py` 的复核系统提示词已写死"主报告只能作基线、不得冒充当前验证"，缺当前证据必须 `data_insufficient` + 缺口码。10/10 测试通过。**建议 Mac 端拉取后用新协议重跑 93 只**。
4. **两轮规则包逐条审计（前 24 只、64 条已完成语义裁决）**：0 条真实阈值冲突、0 条报告外阈值；38% 语义一致，44% 口径不同但均忠于报告（risk 任务两轮常锚定报告不同章节），19% 我方规则夹带基线数据（格式缺陷，非阈值错误）。
5. **需要人工裁决的分歧 17 处**（triggered 类，明细见对照报告），最值得关注的是**恒瑞医疗 risk**：我方按报告字面信号判 triggered，锁定轮判 not_triggered——规则文本"字面触发"与"实质红线"的口径差。

---

## 一、背景与工作范围

Mac 端于 2026-08-29 完成 93 只 A 股的基本面复核批量（`local/fundamental-review-full/`，复核模型 deepseek-v4-flash 经 OpenCode）。Windows 端同步该分支后，开展了四项工作：

1. **试点股全流程验证**（东方电子 000682.SZ）：数值雷达（东财/巨潮交叉验证偏差 0%）+ 由 ZCode 担任语义复核模型，按工具封闭协议产出结论，与 deepseek 逐条一致，并额外标注 2 处数据缺口。
2. **93 只独立规则包复核**：子代理被禁止读取 `main_report_resolutions.json` 与已有结果，只从各主报告正文推导 3 条任务（entry/holder/risk），再按同一封闭协议用本地证据复核。
3. **双轮结果对照**：与 deepseek 锁定规则轮逐股逐任务比对，产出对照报告。
4. **协议修订**：把对照中发现的验证纪律漏洞修进工具本体。

## 二、执行流水线（可复现）

| 阶段 | 脚本/入口 | 产物 |
|---|---|---|
| 工作清单 | `logs/build_zcode_manifest.py` | `logs/zcode_review_manifest.json`（93 只的报告+证据文档映射） |
| 子代理推导+复核 | 12 组并行（受平台并发限制改为每波 2 组） | `local/fundamental-review-zcode/agent_out/`（93 份） |
| 校验+组装 | `logs/assemble_zcode_results.py` | `local/fundamental-review-zcode/full-zcode-rules/`（93 份，279/279 引文逐字比对通过） |
| 结果对照 | `logs/compare_reviews.py` | `local/fundamental-review-zcode/对照报告-20260829.md` |
| 规则自动比对 | `logs/compare_rules.py` | `logs/rule_diff.json`（279 条中 250 条数字集合不同） |
| 规则语义裁决 | 子代理 2 组（因并发限制完成 24/93 只） | `local/fundamental-review-zcode/rule_audit/`（24 份） |

## 三、双轮结果对照（关键数字）

| 状态 | deepseek（锁定规则轮） | ZCode（独立规则轮） |
|---|---|---|
| verified | 126 | 6 |
| data_insufficient | 102 | 252 |
| not_triggered | 34 | 19 |
| triggered | 17 | 2 |

- 一致率：entry 25/93，holder 28/93，risk 48/93；总体 101/279（36%）。
- **结构性原因**：79/93 只股票本地只有主报告。我方严格执行"主报告只作基线"，相关任务一律 `data_insufficient`；deepseek 轮将报告基线值充当了当前验证。`verified vs data_insufficient` 象限反映标准宽严差，不是事实分歧。
- **triggered 类分歧 17 处**（16 处 deepseek 独自 triggered、1 处反向）：长鑫存储 ×3、江波龙 ×2、DapuStor ×2、分众传媒、Jereh、华明装备、特变电工、中航机载、中国西电、montage-tech、工商银行、思源电气、恒瑞医疗。完整明细（含两轮规则要点）见 `对照报告-20260829.md`。
- **恒瑞医疗（600276.SH）risk 案例**：我方规则按报告字面信号（创新药收入 +16.38% 低于 +20%、仿制药 -16.1%）判 triggered；锁定轮判 not_triggered，且其跟踪文档自述"红线 0 项触发的边际弱化"。这是"字面触发 vs 实质红线"的规则文本口径问题，建议人工裁决并回写规则表述。

## 四、两轮规则包审计（规则文本质量）

自动比对：279 条任务中，文本完全一致 0 条，数字阈值集合一致 29 条，不同 250 条。语义裁决（已完成 24 只、64 条）：

| verdict | 条数 | 占比 |
|---|---|---|
| 语义一致（仅措辞/详略不同） | 24 | 38% |
| 口径不同_均忠于报告（risk 任务常一锚"加仓信号"、一锚"卖出信号"表） | 28 | 44% |
| 独立规则混入基线数据（格式缺陷，阈值本身忠于报告） | 12 | 19% |
| 任一方引入报告外阈值 / 真实阈值冲突 / 需人工裁决 | 0 | 0% |

**结论**：两轮规则实质一致，锁定规则无"写错阈值"的证据。质量差异是结构性的：

- 锁定规则**更纯更稳定**（只含条件与阈值），适合作为唯一执行权威——这是对的。
- 独立规则**可核查性更好**：每条附报告原文依据（逐字引用 + 行号），且普遍补入了锁定规则省略的可核查阈值（PE/PB 档、更多卖出信号）。

## 五、协议修订（本次推送的代码变更）

`tools/fundamental_review_radar.py` 中 `review_locked_tasks_with_local_model` 的系统提示词与用户载荷：

- 明确 `main_report_reference` 只用于确认规则基线与报告原文；其历史财务、基线价格、报告日行情**一律不是当前状态证据**。
- 需要当前数值/对比期/事件确认的条件，只有 `local_current_evidence` 文档中存在基线之后记录才可判 `verified/not_triggered/triggered`，否则必须 `data_insufficient` + `missing_codes`。
- schema 中 `status` 字段说明与新增 `verification_policy` 键同步收紧。
- 测试：`tests/test_fundamental_review_radar.py` 10/10 通过，语法检查通过。

## 六、给 Mac 端的行动建议（按优先级）

1. **用新协议重跑 93 只**（OpenCode key 在 Mac 端可用）：`git pull` 后执行 `py -3 tools/fundamental_review_radar.py --all-a-shares`（建议换新输出目录，与旧结果留档对照）。预期 verified 大幅下降、data_insufficient 相应上升——那才是证据纪律下的真实分布。
2. **人工裁决 17 处 triggered 分歧**，优先恒瑞医疗（600276.SH）risk：裁定"字面触发"是否应升级为红线表述，并回写锁定规则。
3. **锁定规则层吸收两个实践**：① 每条规则附 derivation_quote + 报告行号；② 明确 risk 任务锚定的报告章节（加仓信号 vs 卖出信号表），消除两轮最大的系统性二义。
4. **独立规则包的定位**：修掉 12 条夹带数据后，作为锁定规则的质量校验基准（每次人工裁决后跑独立推导做 diff），不建议作为第二套并行执行规则。

## 七、文件清单

**随本报告推送**：
- `tools/fundamental_review_radar.py`（协议修订）
- 本报告：`reports/fundamental-review-radar/fundamental-review-radar-zcode-workreport-20260829.md`
- 执行记录：`logs/build_zcode_manifest.py`、`logs/compare_rules.py`、`logs/compare_reviews.py`、`logs/assemble_zcode_results.py`、`logs/run_zcode_review_000682.py`、`logs/zcode_review_manifest.json`、`logs/rule_diff.json`、`logs/rule_audit_worklist.json`
- 复核结果：`local/fundamental-review-zcode/full-zcode-rules/`（93 份标准结果）、`rule_audit/`（24 份裁决）、`对照报告-20260829.md`、试点股 `000682.SZ.json` 与数值雷达输出

**仅存于 Windows 本地（未推送）**：
- `local/fundamental-review-zcode/agent_out/`（93 份子代理原始输出，内容已被校验后的组装版覆盖，可由流水线重生成）

**注意**：本机工作区另有约 145 个未跟踪的 `data/investment-dashboard/decision_details/*.json`（切分支前本机仪表盘重建产物），与本次工作无关，未提交、未清理。

## 八、局限与诚实性声明

- 独立规则轮的子代理全程未读取人工锁定规则与既有结果；但两者源自**同一批主报告**，收敛性部分来自共同上游。
- 语义裁决覆盖 24/93 只；其余 69 只已完成自动比对（模式与已裁决部分一致），语义裁决可按同流程补完。
- 本地证据多数截止 2026-07 中下旬（thesis/tracker 基线日），复核执行日为 2026-08-29；价格类条件在执行层面需以最新行情复核。
- 全程未修改锁定规则文件与 deepseek 结果（只读）；Windows 端 `windows-dev` 分支的本地提交与 stash 不受影响。
