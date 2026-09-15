---
name: daily-investment-review
description: Run the local AI Berkshire daily A-share sentiment and opportunity review when the user asks to run today's investment review, daily opportunity scan, closing review, or to publish a previously validated local review. Defaults to review without publishing.
---

# Daily Investment Review

Use the current Codex/ChatGPT model as the semantic reasoning plane. Never call
an HTTP LLM API or read DeepSeek, OpenCode, MiMo, OpenAI, or Anthropic API keys.
The legacy API workflow is a separate, explicitly invoked cold backup. Never
fall back to it automatically when local input or review validation fails.

## Modes

- `status`: fetch and verify the latest deterministic A-share input only.
- `review` (default): sync, classify sentiment, review opportunities, challenge
  current/near candidates, and validate. Do not commit or push.
- `review --force`: re-evaluate every packet, then validate. Do not publish.
- `review --ticker 603606.SH`: single-A-share dry-run. It is always marked
  non-publishable and cannot replace the full A-share result set.
- `publish`: publish only the already validated transaction after the user
  explicitly asks. Revalidate first, then exact-stage, commit, push, wait for CI,
  and verify the existing publisher/dashboard path.

## Workflow

1. Locate the real Git root and inspect `git status`. Preserve all pre-existing
   changes. Never reset, clean, restore broadly, or use `git add .`/`git add -A`.
2. Run `scripts/prepare_daily_review.py`. It fetches `vps-generated` without
   merging and verifies the ready marker and packet hashes. The ready marker
   must prove every selected A-share has a current eligible quote, verified raw
   collection, ready non-stale daily technical data, and canonical state. Any
   missing or stale ticker fails closed and must be reported by ticker/reason.
3. For `review`, read [sentiment-contract.md](references/sentiment-contract.md)
   and [opportunity-contract.md](references/opportunity-contract.md). Write one
   review JSON per ticker and one `_shared.json` for shared industry events under
   the transaction's `reviews/` directory. Omit `_shared.json` only when the
   shared packet contains no events. Scripts
   prepare and validate data; they must not manufacture semantic judgments.
4. Run `scripts/validate_local_review.py`. A failure leaves production artifacts
   unchanged. Report the exact missing/invalid ticker and continue repairing the
   staging transaction when safe.
5. Read [safety-boundaries.md](references/safety-boundaries.md) before any apply
   or publish. A successful review ends at `READY_TO_PUBLISH`.
6. Only explicit `publish` may follow [publishing.md](references/publishing.md).

For status/review/publish commands, run scripts from this Skill package and pass
the actual repository root. Keep the transaction in `.runtime/local-review/`.

## Final report

State the data cutoff, Formal/Context sentiment counts, review universe, reused
and re-evaluated counts, current/near/not-current/insufficient counts, challenge
count, and `authority changes = 0`. For review, explicitly say
`commit during review = NO` and `READY_TO_PUBLISH = YES/NO`.
