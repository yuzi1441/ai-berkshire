# Priority 20 Main Report Strong Semantic Review

> Review date: 2026-09-16 (Asia/Shanghai)
>
> Reviewer identity: `current_page_codex_semantic_review`
>
> Authority: candidate only; this audit does not approve a trade or change production Dashboard authority.

## Scope and method

- The review set was derived from Priority 20 rows whose pre-review `publication_status` was `STRONG_REVIEW_REQUIRED` (15 contracts), plus BUY_READY control `600519.SH`.
- Each canonical report path and SHA was verified against `current_reports.json` before review.
- Review covered empty-position versus holder scope, price role, action type, nested logic, prerequisites, hard blocks, multi-market isolation, current versus future paths, and direct report evidence.
- Current prices and current financial facts were not used to reinterpret report semantics.

## Results

| Ticker | Company | Result | Semantic finding |
|---|---|---|---|
| 000400.SZ | 许继电气 | PASS | 20-22元 is explicitly a small observation position; lower entry paths retain their stated AND/OR conditions. |
| 000568.SZ | 泸州老窖 | PASS | 80-85元 aggressive one-third base position and the stable two-confirmation path are correctly separated. |
| 002027.SZ | 分众传媒 | PASS | 4.3-4.8元 is a direct empty-position buy band, not a target price; no mandatory operating prerequisite was omitted. |
| 002028.SZ | 思源电气 | PASS | 125-145元 remains a small research position; review zones were not promoted to formal entry. |
| 002352.SZ | 顺丰控股股份有限公司 | PASS | A-share 30-34元 is only a small trial; A/H prices and the H-share filing condition remain isolated. |
| 002415.SZ | 海康威视 | PASS | 30-34元 observation position retains the cash-flow gate; wording below 30元 remains path-local ambiguous. |
| 300274.SZ | 阳光电源 | PASS | ≤103.55元 is an observation position; the meaningful ≤92.04元 entry keeps its fundamental gate. |
| 600276.SH | 恒瑞医疗 | NEEDS_CLARIFICATION | The report does not uniquely resolve how the tiered price table, the general “fundamentals not deteriorated” premise, and the empty-position “two of three” instruction compose. |
| 600309.SH | 万华化学 | PASS | 70-75元 remains a small trial; the main staged-buy range remains 63-69元. |
| 600426.SH | 华鲁恒升 | PASS | 18-21元 trial correctly requires H1 confirmation; 15-17元 is the stable staged-buy band. |
| 600519.SH | 贵州茅台 | PASS (control) | 1100-1300元 directly permits empty-position staged entry; the 5% profit recovery condition applies to holder add-on. |
| 601127.SH | 赛力斯 | PASS | The report says “one of”; the 45-50元 price branch independently satisfies the ANY path. |
| 601179.SH | 中国西电 | PASS (TRIAL_READY control) | The report explicitly permits a current theme-driven small position with an exit; it remains a trial, not a formal value entry. |
| 603129.SH | 春风动力 | PASS | The report explicitly permits a current half-position staged entry; tariff and ZEEHO items are monitoring items, not stated entry gates. |
| 603288.SH | 海天味业 | PASS | 32-35元 is a tracking/small position; ≤28元 “focus” was not converted into automatic buying. |
| 603606.SH | 东方电缆 | PASS | 36-45元 + at least four of six, and 30-36元 + H1 not negative, are preserved independently of current facts. |
| 688676.SH | 金盘科技 | FAIL → corrected → PASS | “Event-driven small position” had been represented as an unconditional ready path. It is now path-local ambiguous and cannot produce TRIAL_READY. |

## Contract correction

Only `688676.SH` was changed. The report supplies neither a named event nor an executable event threshold for the aggressive small-position path. The path was changed from `ready` to `ambiguous` and added to the existing `NO_EXPLICIT_ACTION_PRICE` ambiguity's `affected_path_ids`. No schema or evaluator behavior changed.

Before correction, the contract could return `TRIAL_READY` from a conditionless path. After correction, it returns `NO_ENTRY_PATH` while preserving the report's unresolved path for later clarification.

## Safety conclusion

- Final approvals: PASS 16, NEEDS_CLARIFICATION 1, unresolved FAIL 0.
- Initial failures retained in review history: 1 (`688676.SH`).
- Contracts regenerated: NO.
- Production Dashboard, Decision Board authority, Action Guidance, main, and VPS: unchanged.
