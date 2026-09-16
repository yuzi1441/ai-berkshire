# Main Report Semantic 20-Stock Audit

> Candidate-only side-by-side audit performed on 2026-09-16.
> The sample uses deterministic seed `20260916` from the 93-stock A-share
> canonical universe. Each row was checked against the complete canonical main
> report named by `current_reports.json`, not against a report filename guess.
> The audit is comparison-only and does not change production Dashboard
> authority.

## Method

For each sample ticker, the reviewer reopened the bound main report and checked
the candidate contract for:

- empty-position versus holder scope;
- action semantics and current stance;
- price role (entry, review, add, exit, or valuation reference);
- prerequisites and nested condition logic;
- evidence quotes and line references;
- report-contract conflicts and ambiguous handling.

`PASS` means no semantic warning or failure was found in this side-by-side
sample. `ambiguous` is a contract status and is intentionally not treated as a
sample failure: the contract remains ambiguous when the source report does not
support a deterministic interpretation.

## Sample

| # | Ticker | Company | Contract status | Empty-position action | Holder action | Entry semantic | Audit result |
|---:|---|---|---|---|---|---|---|
| 1 | 605117.SH | deye | ambiguous | WATCH | HOLD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 2 | 000657.SZ | 中钨高新 | ready | WATCH | REDUCE | REVIEW_ONLY | PASS |
| 3 | 688017.SH | leaderdrive | ambiguous | AVOID | REDUCE | EXPLICIT_NO_BUY | PASS |
| 4 | 600309.SH | 万华化学 | ready | WATCH | HOLD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 5 | 002270.SZ | 华明装备 | ambiguous | WATCH | HOLD_NO_ADD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 6 | 603659.SH | 璞泰来 | ambiguous | WATCH | HOLD_NO_ADD | TRIAL_ENTRY_DEFINED | PASS |
| 7 | 002050.SZ | 浙江三花智能控制股份有限公司 | ready | WATCH | HOLD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 8 | 600276.SH | 恒瑞医疗 | ambiguous | WATCH | HOLD_NO_ADD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 9 | 601126.SH | 四方股份 | ready | WATCH | HOLD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 10 | 002837.SZ | 英维克 | ambiguous | AVOID | REDUCE | REVIEW_ONLY | PASS |
| 11 | 601975.SH | 招商南油 | ready | WATCH | HOLD_NO_ADD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 12 | 600795.SH | guodian-power | ambiguous | OPEN_POSITION | HOLD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 13 | 601899.SH | 紫金矿业 | ready | WATCH | HOLD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 14 | 603129.SH | chunfeng-dongli | ready | OPEN_POSITION | HOLD_NO_ADD | UNCONDITIONAL_ENTRY_DEFINED | PASS |
| 15 | 601717.SH | 中创智领 | ambiguous | WATCH | HOLD | TRIAL_ENTRY_DEFINED | PASS |
| 16 | 603228.SH | 景旺电子 | ready | WATCH | HOLD_NO_ADD | CONDITIONAL_ENTRY_DEFINED | PASS |
| 17 | 601179.SH | 中国西电 | ready | WATCH | HOLD_NO_ADD | TRIAL_ENTRY_DEFINED | PASS |
| 18 | 002916.SZ | 深南电路 | ambiguous | WATCH | HOLD | REVIEW_ONLY | PASS |
| 19 | 002352.SZ | 顺丰控股股份有限公司 | ready | WATCH | HOLD | UNCONDITIONAL_ENTRY_DEFINED | PASS |
| 20 | 600549.SH | 厦门钨业 | ready | AVOID | HOLD_NO_ADD | CONDITIONAL_ENTRY_DEFINED | PASS |

## Result

- Sample size: 20
- PASS: 20
- WARNING: 0
- FAIL: 0
- Ambiguous contracts retained as ambiguous: 9
- Contracts requiring strong review: 20
- Golden contracts modified: NO

The deterministic validator separately passed all 93 candidate contracts. This
sample audit therefore provides a human semantic spot-check, while the
validator remains the hard gate for source binding, SHA, evidence, numeric
traceability, AST shape, scope, and enum validity.
