# Sentiment contract

Classify every event listed by `sentiment_review_plan.classify_event_ids`.
Events in `reuse_event_ids` are already contract-bound and must not be rewritten.
Return one record for every exact `event_id` with direction (-1 to 1), impact
(1 to 5), relevance (0 to 1), confidence (0 to 1), event_type, and reason.

Company events are written to each ticker review. Shared industry events from
`shared.json` are classified exactly once in `_shared.json`, then the validator
projects the resulting industry sentiment to every company in that industry.
Never repeat an industry classification in each company review.

- A/B are Formal Evidence. C/D are Context Evidence and never contribute to
  Formal Sentiment or `score_0_100`.
- The packet already clusters deterministic duplicates. Treat a cluster as one
  event regardless of `duplicate_count`.
- Important A/B events require `verification` when impact >= 4, confidence <
  0.6, absolute direction >= 0.75, or relevance < 0.6. Verification must use
  `confirm`, `downgrade`, or `reject`, with a reason. It may not upgrade.
- Challenge title hype, company mismatch, duplicate identity, industry-to-stock
  over-attribution, rumors, exaggerated long-term meaning, and wrong direction.

The validator deterministically aggregates classifications. Do not invent IDs
and do not calculate a Formal score from C/D evidence.
