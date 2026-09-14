# Safety boundaries

Local review may create only sentiment and opportunity analysis artifacts. It
must never modify Canonical reports, Original Buy Thesis, holdings, cost basis,
position weight, Drift authority, Decision Rules, Checklist authority, report
judgments, lifecycle, or Action Guidance.

Keep work in `.runtime/local-review/<date>/` until validation succeeds. An
interrupted or invalid review leaves published artifacts unchanged.

Never stage or remove `data/investment-dashboard/current_reports.migration.json`.
Preserve every other pre-existing change. Opportunity is research attention,
not an executable buy/sell/weight/stop/target instruction.
