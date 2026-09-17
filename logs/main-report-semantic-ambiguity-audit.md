# Main Report Semantic Ambiguity Audit (Schema v2)

Date: 2026-09-16

This audit is a deterministic reclassification of the 93 existing A-share
candidate contracts. No report was regenerated and no model/API was invoked.

## Result

- Original contract-global `ambiguous`: **53**
- v2 contract status: **40 ready / 53 partial / 0 ambiguous / 0 error**
- Empty-position scope: **64 ready / 24 partial / 5 ambiguous**
- Empty-position safely evaluable: **88**
- Empty-position blocked by semantic ambiguity: **5**

The 53 legacy global ambiguities have the following mutually exclusive primary
classification (classification precedence is entry-blocking, global,
path-local, holder, exit/reduce, monitoring):

- Entry-affecting and scope-blocking: **5**
- Holder-only: **4**
- Exit/reduce-only (including one exit + monitoring case): **21**
- Monitoring-only: **1**
- Path-local entry ambiguity with other clear paths preserved: **12**
- True cross-scope/global conflict: **10**

The 24 contracts carrying `affects_entry=true` consist of the five blocked
empty-position scopes plus localized unresolved entry/review paths. A localized
ambiguous path does not erase a separate ready path; the evaluator returns the
safe known result and exposes `unresolved_path_ids` and warnings.

## Entry Semantic Ambiguity (Fail Closed)

These five remain `ENTRY_SEMANTIC_AMBIGUOUS` for empty-position evaluation:

- `000858.SZ` 五粮液 — “三大重估信号”与五项清单冲突。
- `600089.SH` 特变电工 — 正文/底部契约及价格带动作边界冲突。
- `600183.SH` 生益科技 — “再重估”不能确定为正式建仓。
- `601398.SH` 工商银行 — 当前区间观望与小仓配置缺少选择规则。
- `603005.SH` 晶方科技 — 两组行动价格带冲突。

## Scope Regression

- `000568.SZ` 泸州老窖: `empty_position=ready`, `holder=ambiguous`.
- The 80–85 trial path and the <=90 plus two confirmations entry path remain
  evaluable.
- `MISSING_HOLDER_ACTION` does not contaminate empty-position entry evaluation.

## Safety Boundary

`partial` means that some scope/path remains unresolved while independently
supported semantics remain usable. It is not a promotion to `ready`. Every
unresolved item retains report evidence, scope/path attachment and strong-review
routing.
