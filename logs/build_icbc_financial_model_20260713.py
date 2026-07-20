"""Build the ICBC financial history and exact valuation evidence bundle."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path


DATA_DIR = Path("data/601398")
RAW_PATH = DATA_DIR / "eastmoney_finance_snapshot_20260713.json"
TOOL = Path("tools/financial_rigor.py")


raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
records = {
    int(item["REPORT_YEAR"]): item
    for item in raw["data"]
    if item.get("REPORT_TYPE") == "年报" and str(item.get("REPORT_YEAR", "")).isdigit()
}


def yi(value):
    return None if value is None else round(float(value) / 100_000_000, 4)


history = []
for year in range(2021, 2026):
    item = records[year]
    history.append(
        {
            "year": year,
            "revenue_100m_cny": yi(item.get("TOTALOPERATEREVE")),
            "parent_net_profit_100m_cny": yi(item.get("PARENTNETPROFIT")),
            "eps_cny": item.get("EPSJB"),
            "bvps_cny": item.get("BPS"),
            "roe_pct": item.get("ROEJQ"),
            "roa_pct": item.get("ZZCJLL"),
            "net_interest_margin_pct": item.get("NET_INTEREST_MARGIN"),
            "net_interest_spread_pct": item.get("NET_INTEREST_SPREAD"),
            "npl_ratio_pct": item.get("NONPERLOAN"),
            "provision_coverage_pct": item.get("BLDKBBL"),
            "cet1_ratio_pct": item.get("HXYJBCZL"),
            "capital_adequacy_pct": item.get("NEWCAPITALADER"),
            "cost_income_ratio_pct": item.get("REVENUE_RATIO"),
            "gross_loans_100m_cny": yi(item.get("GROSSLOANS")),
            "portal_deposits_100m_cny": yi(item.get("TOTALDEPOSITS")),
        }
    )


with (DATA_DIR / "financial_history_2021_2025.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as handle:
    writer = csv.DictWriter(handle, fieldnames=list(history[0]))
    writer.writeheader()
    writer.writerows(history)


cross_sources = {
    "2025_revenue_100m_cny": {
        "annual_report_cninfo": 8382.70,
        "eastmoney_f10": 8382.70,
        "akshare_financial_abstract": 8382.70,
    },
    "2025_parent_net_profit_100m_cny": {
        "annual_report_cninfo": 3685.62,
        "eastmoney_f10": 3685.62,
        "akshare_financial_abstract": 3685.62,
    },
    "2026_q1_revenue_100m_cny": {
        "q1_report_cninfo": 2303.70,
        "akshare_financial_abstract": 2303.70,
    },
    "2026_q1_parent_net_profit_100m_cny": {
        "q1_report_cninfo": 869.41,
        "akshare_financial_abstract": 869.41,
    },
    "2026_07_13_a_share_close_cny": {"tencent": 7.53, "sina": 7.53},
    "2026_07_13_h_share_close_hkd": {"tencent": 6.83, "sina": 6.83},
}
(DATA_DIR / "cross_validation_sources_20260713.json").write_text(
    json.dumps(cross_sources, ensure_ascii=False, indent=2), encoding="utf-8"
)


checks = []
for field, values in cross_sources.items():
    unit = "亿元" if "100m" in field else ("港元" if "h_share" in field else "元")
    checks.append(
        (
            f"cross_validate_{field}",
            [
                "cross-validate",
                "--field",
                field,
                "--values",
                json.dumps(values, ensure_ascii=False),
                "--unit",
                unit,
            ],
        )
    )


checks.extend(
    [
        (
            "verify_a_equivalent_market_cap",
            [
                "verify-market-cap",
                "--price",
                "7.53",
                "--shares",
                "356406257089",
                "--reported",
                "2683739000000",
                "--currency",
                "CNY",
            ],
        ),
        (
            "verify_h_share_market_cap",
            [
                "verify-market-cap",
                "--price",
                "6.83",
                "--shares",
                "86794044550",
                "--reported",
                "592803320000",
                "--currency",
                "HKD",
            ],
        ),
        (
            "verify_2025_valuation",
            [
                "verify-valuation",
                "--price",
                "7.53",
                "--eps",
                "1.00",
                "--bvps",
                "10.83",
                "--dividend",
                "0.3103",
            ],
        ),
        (
            "three_scenario_eps_pe",
            [
                "three-scenario",
                "--price",
                "7.53",
                "--eps",
                "1.00",
                "--shares",
                "3564.06257089",
                "--growth",
                "0.05",
                "0.02",
                "-0.02",
                "--pe",
                "9",
                "8",
                "6",
                "--years",
                "3",
                "--currency",
                "CNY",
            ],
        ),
        (
            "calc_2026_q1_bvps_excluding_other_equity",
            [
                "calc",
                "--expr",
                "(4327391 - 384657) / 356406.257089",
            ],
        ),
        (
            "calc_current_pb_on_2026_q1_bvps",
            [
                "calc",
                "--expr",
                "7.53 / ((4327391 - 384657) / 356406.257089)",
            ],
        ),
        (
            "calc_2021_2025_revenue_cagr",
            ["calc", "--expr", "(8382.70 / 9427.62) ** (1 / 4) - 1"],
        ),
        (
            "calc_2021_2025_parent_profit_cagr",
            ["calc", "--expr", "(3685.62 / 3483.38) ** (1 / 4) - 1"],
        ),
        (
            "calc_2021_2025_bvps_cagr",
            ["calc", "--expr", "(10.83 / 8.15) ** (1 / 4) - 1"],
        ),
    ]
)


env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
sections = []
for label, args in checks:
    result = subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    note = ""
    if label == "verify_2025_valuation":
        note = "Input note: EPS is 2025A static EPS; the tool's TTM label is generic.\n\n"
    elif label == "three_scenario_eps_pe":
        note = "Input note: target prices are 2028 year-end values before dividends, not current fair values.\n\n"
    sections.append(f"## {label}\n\n{note}{result.stdout.strip()}\n")
(DATA_DIR / "financial_rigor_checks_20260713.txt").write_text(
    "\n".join(sections), encoding="utf-8"
)


latest_bvps = Decimal("11.062471327531828")
scenarios = {
    "method": "bank_valuation_cross_checks",
    "latest_bvps_cny": str(latest_bvps),
    "bvps_formula": "(2026Q1 parent equity - preference shares - perpetual bonds) / exact ordinary shares",
    "as_of": "2026-07-13",
    "eps_pe_2028_target_scenarios": [
        {"name": "bull", "eps_growth": "0.05", "target_pe": "9", "target_price_cny": "10.42"},
        {"name": "base", "eps_growth": "0.02", "target_pe": "8", "target_price_cny": "8.49"},
        {"name": "bear", "eps_growth": "-0.02", "target_pe": "6", "target_price_cny": "5.65"},
    ],
    "eps_pe_note": "2028 year-end prices before dividends; not current fair values",
    "residual_income_consistency_checks": [],
}
for name, roe, payout, cost in (
    ("base_current_31pct_payout", Decimal("0.088"), Decimal("0.31"), Decimal("0.105")),
    ("base_normalized_50pct_payout", Decimal("0.088"), Decimal("0.50"), Decimal("0.105")),
):
    growth = roe * (Decimal("1") - payout)
    justified_pb = (roe - growth) / (cost - growth)
    scenarios["residual_income_consistency_checks"].append(
        {
            "name": name,
            "sustainable_roe": str(roe),
            "payout_ratio": str(payout),
            "implied_growth": str(growth),
            "cost_of_equity": str(cost),
            "justified_pb": str(justified_pb.quantize(Decimal("0.0001"))),
            "fair_value_cny": str((latest_bvps * justified_pb).quantize(Decimal("0.01"))),
        }
    )
scenarios["pb_reference_bands"] = {
    "high_margin_of_safety_pb_0.55_to_0.60_cny": [
        str((latest_bvps * Decimal("0.55")).quantize(Decimal("0.01"))),
        str((latest_bvps * Decimal("0.60")).quantize(Decimal("0.01"))),
    ],
    "reasonable_pb_0.60_to_0.75_cny": [
        str((latest_bvps * Decimal("0.60")).quantize(Decimal("0.01"))),
        str((latest_bvps * Decimal("0.75")).quantize(Decimal("0.01"))),
    ],
    "central_pb_0.65_to_0.75_cny": [
        str((latest_bvps * Decimal("0.65")).quantize(Decimal("0.01"))),
        str((latest_bvps * Decimal("0.75")).quantize(Decimal("0.01"))),
    ],
    "fuller_pb_0.85_to_0.95_cny": [
        str((latest_bvps * Decimal("0.85")).quantize(Decimal("0.01"))),
        str((latest_bvps * Decimal("0.95")).quantize(Decimal("0.01"))),
    ],
}
scenarios["current_metrics"] = {
    "price_cny": "7.53",
    "pb_on_2026_q1_bvps": str((Decimal("7.53") / latest_bvps).quantize(Decimal("0.0001"))),
    "dividend_yield_on_2025_dps": str(
        (Decimal("0.3103") / Decimal("7.53")).quantize(Decimal("0.000001"))
    ),
}
scenarios["recommended_interpretation"] = {
    "current_fair_value_range_cny": ["6.80", "8.30"],
    "stress_range_cny": ["6.40", "8.60"],
    "high_margin_of_safety_buy_at_or_below_cny": ["6.40", "6.60"],
    "note": "Ranges synthesize residual-income consistency, historical/peer PB, and 2028 EPS-PE targets.",
}
(DATA_DIR / "valuation_assumptions_20260713.json").write_text(
    json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8"
)


print(json.dumps({"history_rows": len(history), "checks": len(checks), "valuation": scenarios}, ensure_ascii=False, indent=2))
