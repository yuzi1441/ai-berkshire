#!/usr/bin/env python3
"""Refresh price-only projections independently of formal/research evaluation.

Called under the existing scheduler lock. Static rules are rebuilt only by a
full release build. The core is published last and atomically for browser readers.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import dashboard_snapshot
import build_local_price_trigger_dashboard as price


def refresh(repo_root: Path, evaluated_at: datetime | None = None) -> dict:
    data = repo_root / "data/investment-dashboard"
    public = repo_root / "site/data"
    core = price.load_json(public / dashboard_snapshot.FILENAME)
    dashboard_snapshot.validate_snapshot(core)
    rules = price.load_json(data / "price_trigger_rules.json")
    errors = price.validate_price_rules(rules, set(price.discover_contract_tickers(repo_root)), production=True)
    errors += price.validate_price_rule_bindings(rules, repo_root)
    if errors:
        raise ValueError("Stale price rules: " + "; ".join(errors))
    layer = price.match_price_triggers(rules, price.load_json(data / "quotes/latest.json"),
                                       evaluated_at or datetime.now(price.SHANGHAI), production=True)
    by_ticker = {row["ticker"]: row for row in layer["companies"]}
    companies = core["companyState"]["companies"]
    identities = {row["ticker"]: row["company"] for row in companies}
    if any(identities.get(ticker) != row["company"] for ticker, row in by_ticker.items()):
        raise ValueError("Price/core company binding mismatch")
    for row in companies:
        if row["ticker"] in by_ticker:
            row["price_trigger_shadow"] = by_ticker[row["ticker"]]
    core["companyState"]["price_trigger_daily"] = {
        key: layer[key] for key in ("authority", "production_consumable", "generated_at",
                                    "price_cutoff", "company_count", "state_counts")
    }
    core["companyState"]["price_trigger_daily"]["investment_eligibility"] = False
    for directory in (data, public):
        price._write_json(directory / "price_triggers.json", layer)
        price._write_json(directory / "company_state.json", core["companyState"])
    dashboard_snapshot.publish_snapshot(public / dashboard_snapshot.FILENAME,
        board=core["board"], layers={"state": core["companyState"], "rules": core["rules"],
                                    "technical": core["technical"]},
        tracking=core["tracking"], original_theses=core["originalTheses"])
    return layer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = refresh(args.repo_root.resolve())
    print(result["state_counts"])
