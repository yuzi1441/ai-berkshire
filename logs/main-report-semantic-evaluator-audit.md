# Main Report Semantic Evaluator Audit (Schema v2)

Date: 2026-09-16

These are deterministic dry evaluations using existing candidate contracts and
explicit fixture facts. They are state-machine tests, **not current market or
investment conclusions**.

## State Samples

| State | Contract | Fixture meaning |
|---|---|---|
| `BUY_READY` | `000333.SZ` 美的集团 | A-share price 65, unconditional entry price path |
| `TRIAL_READY` | `000568.SZ` 泸州老窖 | price 82, clear 80–85 trial path |
| `PRICE_MATCHED_CONDITIONS_PENDING` | `603606.SH` 东方电缆 | price 40, H1 condition facts absent, hard block explicitly false |
| `PRICE_MATCHED_CONDITIONS_NOT_MET` | `000568.SZ` 泸州老窖 | price 88, one required operating confirmation false |
| `CONDITIONS_MET_PRICE_PENDING` | `000568.SZ` 泸州老窖 | both operating confirmations true, price absent |
| `PRICE_NOT_REACHED` | `000568.SZ` 泸州老窖 | operating confirmations true, price 100 |
| `REVIEW_ZONE` | `002837.SZ` 英维克 | price 28, report-defined review zone only |
| `HARD_BLOCKED` | `603606.SH` 东方电缆 | entry facts true and report hard block true |
| `HARD_BLOCK_PENDING` | `603606.SH` 东方电缆 | entry facts true and hard-block fact unknown |
| `EXPLICIT_NO_BUY` | `002272.SZ` 川润股份 | explicit no-buy contract |
| `NO_ENTRY_PATH` | `601919.SH` 中远海控 | no empty-position entry path defined |
| `ENTRY_SEMANTIC_AMBIGUOUS` | `000858.SZ` 五粮液 | empty-position semantic conflict remains unresolved |

Fixture count: one sample for each state above. `NOT_EVALUATED` is separately
covered by the unsupported-v1 regression and is not a business outcome.

## Required Regressions

- 东方电缆: 36–45 + at least 4 of 6 remains conditional; 30–36 + H1 not
  negative remains conditional; price alone returns pending, never buy-ready.
- 泸州老窖: holder ambiguity does not block the two clear empty-position paths.
- 美的集团: <=75.27 trial, 68–71 conditional, <=65.87 unconditional and 75–88
  review remain distinct.
- Review-only: 英维克 returns `REVIEW_ZONE`, not a buy state.
- Explicit no-buy: 川润股份 returns `EXPLICIT_NO_BUY`.
- AT_LEAST_N: 东方电缆's 4-of-6 AST remains intact.
- Multi-market: 中国神华 A-share evaluation does not consume H-share paths.
- Path-local ambiguity: 恒瑞医疗's ready 43–46 entry can evaluate while the
  unresolved two-of-three review path remains exposed in `unresolved_path_ids`.

## Priority and Fail-Closed Rules

1. A true hard block overrides every entry path.
2. An unknown hard block can never produce `BUY_READY` or `TRIAL_READY`.
3. Ordinary prerequisite false is not a hard block.
4. A matched review/watch price is never promoted to entry.
5. Holder ambiguity cannot block an otherwise ready empty-position scope.
6. Global empty-position ambiguity returns `ENTRY_SEMANTIC_AMBIGUOUS`.
7. H-share paths are excluded from A-share evaluation.
