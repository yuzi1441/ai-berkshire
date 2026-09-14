# Opportunity contract

For each `reevaluate` packet, produce `initial` with opportunity_state, why_now,
satisfied_conditions, unmet_conditions, supporting_evidence,
risks_or_counterevidence, evidence_refs, and high/medium/low confidence.

Allowed states: 当前机会、临近机会、暂不构成当前机会、证据不足. Every
reference must use an exact event ID, rule, Checklist gate, or report path from
`evidence_catalog`; invented references fail validation.

Current opportunity requires an already occurred positive material change and
must answer “why now”. Quality, popularity, price decline, technical bounce,
cheap-looking valuation, or possible future catalysts are insufficient alone.
Near opportunity requires a partly satisfied trigger and a decisive remainder.

Current/near Initial requires a separate `challenge` with decision
confirm/downgrade/reject and a full assessment. Challenge Checklist vetoes,
redlines, conflicts, stale evidence, Formal-vs-Context confusion, Drift, dates,
and completeness. It cannot promote near to current. Non-candidates omit it.

For `reuse` packets, do not create a new opportunity judgment; the validator
carries the bound previous result.
