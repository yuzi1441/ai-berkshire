#!/usr/bin/env python3
"""Export point-in-time CSI 300 data from the JoinQuant research environment.

This file is intended to be pasted into a JoinQuant research notebook. It does
not use credentials and does not require jqdatasdk. The default test mode is
deliberately small; set TEST_MODE = False after the test CSVs look correct.

Output files:
    hs300_constituents_2010_2025.csv
    hs300_daily_2010_2025.csv
    hs300_export_manifest.json

The daily file contains only rows for stocks that were members of CSI 300 on
that trading date. Prices use fq='none' and include the provider's trading
status and limit prices so a backtest can apply execution constraints without
reconstructing them from today's rules.
"""

import json
import os
from datetime import date, datetime

import pandas as pd


# ----------------------------- user configuration --------------------------
START_DATE = "2010-01-01"
END_DATE = "2025-12-31"
INDEX_CODE = "000300.XSHG"

# Run the small smoke test first. Change this to False for the full export.
TEST_MODE = True
TEST_MAX_DAYS = 20
TEST_MAX_CODES = 5

# A 20-trading-day probe is enough for the normal semi-annual CSI 300 review
# cycle while keeping the number of get_index_stocks calls manageable.
CONSTITUENT_PROBE_DAYS = 20
PRICE_BATCH_SIZE = 20
OUTPUT_DIR = "."

CONSTITUENT_FILENAME = "hs300_constituents_2010_2025.csv"
DAILY_FILENAME = "hs300_daily_2010_2025.csv"
MANIFEST_FILENAME = "hs300_export_manifest.json"

DAILY_COLUMNS = [
    "trade_date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "money",
    "pre_close",
    "high_limit",
    "low_limit",
    "paused",
    "is_st",
]


# JoinQuant research injects provider functions into the top-level notebook
# namespace. Bind them here before entering helper functions.
try:
    jq_get_all_trade_days = get_all_trade_days
except NameError:
    jq_get_all_trade_days = None
try:
    jq_get_trade_days = get_trade_days
except NameError:
    jq_get_trade_days = None
try:
    jq_get_index_stocks = get_index_stocks
except NameError:
    jq_get_index_stocks = None
try:
    jq_get_index_weights = get_index_weights
except NameError:
    jq_get_index_weights = None
try:
    jq_get_price = get_price
except NameError:
    jq_get_price = None
try:
    jq_get_extras = get_extras
except NameError:
    jq_get_extras = None


def date_text(value):
    """Convert JoinQuant/Pandas date-like values to YYYY-MM-DD text."""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def clean_codes(values):
    """Return stable, de-duplicated security codes."""
    result = []
    seen = set()
    for value in values:
        code = str(value)
        if code not in seen:
            result.append(code)
            seen.add(code)
    return result


def get_trade_dates():
    """Load the requested trading calendar, with a smaller test window."""
    # Research notebooks expose get_all_trade_days more consistently than the
    # strategy-only get_trade_days helper.
    if jq_get_all_trade_days is not None:
        all_days = jq_get_all_trade_days()
        trade_days = [
            day
            for day in all_days
            if START_DATE <= date_text(day) <= END_DATE
        ]
    elif jq_get_trade_days is not None:
        trade_days = list(jq_get_trade_days(start_date=START_DATE, end_date=END_DATE))
    else:
        # The research notebook may expose neither calendar helper. The index
        # daily series still provides the exact trading dates for this export.
        if jq_get_price is None:
            raise RuntimeError("JoinQuant did not expose a trading-calendar or price API.")
        calendar_frame = jq_get_price(
            INDEX_CODE,
            start_date=START_DATE,
            end_date=END_DATE,
            frequency="daily",
            fields=["close"],
            fq="none",
            skip_paused=False,
            fill_paused=False,
            panel=False,
        )
        if calendar_frame is None or len(calendar_frame) == 0:
            trade_days = []
        else:
            date_columns = [
                column
                for column in calendar_frame.columns
                if str(column).lower() in ("time", "date", "trade_date", "datetime")
            ]
            if date_columns:
                trade_days = list(calendar_frame[date_columns[0]])
            else:
                trade_days = list(calendar_frame.index)
    if TEST_MODE:
        trade_days = trade_days[:TEST_MAX_DAYS]
    if not trade_days:
        raise RuntimeError("No trading days were returned for the requested range.")
    return trade_days


def fetch_membership(trade_day, cache):
    """Fetch and cache one historical CSI 300 constituent set."""
    key = date_text(trade_day)
    if key not in cache:
        if jq_get_index_stocks is None:
            raise RuntimeError("JoinQuant did not expose get_index_stocks.")
        codes = jq_get_index_stocks(INDEX_CODE, date=key)
        cache[key] = set(clean_codes(codes))
        print("membership", key, len(cache[key]))
    return cache[key]


def find_first_change(trade_days, left_index, right_index, old_members, cache):
    """Binary-search the first trading day whose membership differs."""
    left = left_index + 1
    right = right_index
    while left < right:
        middle = (left + right) // 2
        if fetch_membership(trade_days[middle], cache) == old_members:
            left = middle + 1
        else:
            right = middle
    return left


def collect_membership_snapshots(trade_days):
    """Find historical membership change dates without using today's index."""
    cache = {}
    first_members = fetch_membership(trade_days[0], cache)
    snapshots = [(trade_days[0], first_members)]
    last_confirmed_index = 0
    last_members = first_members

    while last_confirmed_index < len(trade_days) - 1:
        probe_index = min(
            last_confirmed_index + CONSTITUENT_PROBE_DAYS,
            len(trade_days) - 1,
        )
        probe_members = fetch_membership(trade_days[probe_index], cache)
        if probe_members == last_members:
            last_confirmed_index = probe_index
            continue

        change_index = find_first_change(
            trade_days,
            last_confirmed_index,
            probe_index,
            last_members,
            cache,
        )
        change_members = fetch_membership(trade_days[change_index], cache)
        snapshots.append((trade_days[change_index], change_members))
        print("membership change", date_text(trade_days[change_index]), len(change_members))
        last_confirmed_index = change_index
        last_members = change_members

    return snapshots, cache


def normalize_weight_frame(raw, fallback_date):
    """Normalize get_index_weights output across JoinQuant table variants."""
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=["code", "weight", "display_name", "weight_date"])

    frame = raw.copy()
    if isinstance(frame.index, pd.MultiIndex) or frame.index.name is not None:
        frame = frame.reset_index()
    else:
        # Some JoinQuant versions return a code index without naming it.
        frame = frame.reset_index()

    rename_map = {}
    for column in frame.columns:
        name = str(column).lower()
        if name in ("security", "security_code", "stock_code", "symbol"):
            rename_map[column] = "code"
        elif name in ("date", "weight_date"):
            rename_map[column] = "weight_date"
        elif name in ("weight", "index_weight"):
            rename_map[column] = "weight"
        elif name in ("display_name", "name", "security_name"):
            rename_map[column] = "display_name"
    frame = frame.rename(columns=rename_map)

    if "code" not in frame.columns:
        if "index" in frame.columns:
            frame = frame.rename(columns={"index": "code"})
        else:
            raise RuntimeError("get_index_weights returned no security code column.")
    if "weight" not in frame.columns:
        frame["weight"] = None
    if "display_name" not in frame.columns:
        frame["display_name"] = ""
    if "weight_date" not in frame.columns:
        frame["weight_date"] = fallback_date

    frame["code"] = frame["code"].astype(str)
    frame["weight_date"] = frame["weight_date"].map(date_text)
    return frame[["code", "weight", "display_name", "weight_date"]]


def fetch_weights(snapshot_date, expected_codes, warnings):
    """Fetch the nearest available JoinQuant weight snapshot for one date."""
    fallback_date = date_text(snapshot_date)
    try:
        if jq_get_index_weights is None:
            raise RuntimeError("JoinQuant did not expose get_index_weights.")
        raw = jq_get_index_weights(INDEX_CODE, date=fallback_date)
    except Exception as error:
        warnings.append("weights {}: {}".format(fallback_date, error))
        raw = None

    frame = normalize_weight_frame(raw, fallback_date)
    if len(frame) == 0:
        return {
            code: {"weight": None, "display_name": "", "weight_date": ""}
            for code in expected_codes
        }

    frame = frame.drop_duplicates(subset=["code"], keep="last")
    values = {}
    for code in expected_codes:
        match = frame[frame["code"] == code]
        if len(match) == 0:
            values[code] = {"weight": None, "display_name": "", "weight_date": ""}
            continue
        row = match.iloc[-1]
        values[code] = {
            "weight": row.get("weight"),
            "display_name": row.get("display_name", ""),
            "weight_date": row.get("weight_date", ""),
        }
    return values


def build_constituent_rows(snapshots, warnings):
    """Expand membership snapshots into the requested long CSV schema."""
    rows = []
    for snapshot_date, members in snapshots:
        codes = sorted(members)
        weights = fetch_weights(snapshot_date, codes, warnings)
        effective_date = date_text(snapshot_date)
        for code in codes:
            value = weights.get(code, {})
            rows.append(
                {
                    "effective_date": effective_date,
                    "code": code,
                    "display_name": value.get("display_name", ""),
                    "weight": value.get("weight"),
                    "weight_date": value.get("weight_date", ""),
                    "membership_source": "JoinQuant get_index_stocks",
                    "weight_source": "JoinQuant get_index_weights",
                }
            )
    columns = [
        "effective_date",
        "code",
        "display_name",
        "weight",
        "weight_date",
        "membership_source",
        "weight_source",
    ]
    return pd.DataFrame(rows, columns=columns)


def normalize_price_frame(raw, requested_codes):
    """Normalize panel=False get_price output to one row per code/date."""
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=DAILY_COLUMNS[:-1])

    frame = raw.copy()
    if isinstance(frame.index, pd.MultiIndex):
        frame = frame.reset_index()
    elif not any(str(column).lower() in ("time", "date", "trade_date") for column in frame.columns):
        frame = frame.reset_index()

    rename_map = {}
    for column in frame.columns:
        name = str(column).lower()
        if name in ("time", "date", "datetime"):
            rename_map[column] = "trade_date"
        elif name in ("security", "security_code", "stock_code", "symbol"):
            rename_map[column] = "code"
    frame = frame.rename(columns=rename_map)

    if "trade_date" not in frame.columns:
        frame.insert(0, "trade_date", "")
    if "code" not in frame.columns:
        if len(requested_codes) == 1:
            frame.insert(1, "code", requested_codes[0])
        else:
            raise RuntimeError("get_price returned no security code column for a batch.")

    frame["trade_date"] = frame["trade_date"].map(date_text)
    frame["code"] = frame["code"].astype(str)
    for column in DAILY_COLUMNS[2:-1]:
        if column not in frame.columns:
            frame[column] = None
    return frame[[column for column in DAILY_COLUMNS[:-1] if column in frame.columns]]


def normalize_st_frame(raw):
    """Convert wide get_extras is_st output into trade_date/code/is_st rows."""
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=["trade_date", "code", "is_st"])
    frame = raw.copy()
    frame.index.name = "trade_date"
    frame = frame.reset_index().melt(
        id_vars=["trade_date"], var_name="code", value_name="is_st"
    )
    frame["trade_date"] = frame["trade_date"].map(date_text)
    frame["code"] = frame["code"].astype(str)
    return frame


def active_membership_by_date(snapshots, trade_days):
    """Build a date-to-code-set map from effective-date snapshots."""
    result = {}
    snapshot_index = 0
    active = set()
    ordered = sorted(snapshots, key=lambda item: date_text(item[0]))
    for trade_day in trade_days:
        current_text = date_text(trade_day)
        while snapshot_index < len(ordered) and date_text(ordered[snapshot_index][0]) <= current_text:
            active = ordered[snapshot_index][1]
            snapshot_index += 1
        result[current_text] = active
    return result


def date_ranges(start_date, end_date):
    """Yield calendar-year ranges within the requested period."""
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    for year in range(start_year, end_year + 1):
        left = max(start_date, "{}-01-01".format(year))
        right = min(end_date, "{}-12-31".format(year))
        if left <= right:
            yield left, right


def fetch_daily_batch(codes, start_date, end_date, active_by_date, warnings):
    """Fetch one price/ST batch and retain only point-in-time members."""
    try:
        if jq_get_price is None:
            raise RuntimeError("JoinQuant did not expose get_price.")
        raw_price = jq_get_price(
            codes,
            start_date=start_date,
            end_date=end_date,
            frequency="daily",
            fields=[
                "open",
                "high",
                "low",
                "close",
                "volume",
                "money",
                "pre_close",
                "high_limit",
                "low_limit",
                "paused",
            ],
            skip_paused=False,
            fq="none",
            fill_paused=False,
            panel=False,
        )
        prices = normalize_price_frame(raw_price, codes)
    except Exception as error:
        warnings.append("price {}..{} {}: {}".format(start_date, end_date, len(codes), error))
        return pd.DataFrame(columns=DAILY_COLUMNS)

    if len(prices) == 0:
        return pd.DataFrame(columns=DAILY_COLUMNS)

    try:
        if jq_get_extras is None:
            raise RuntimeError("JoinQuant did not expose get_extras.")
        raw_st = jq_get_extras(
            "is_st",
            codes,
            start_date=start_date,
            end_date=end_date,
            df=True,
        )
        st = normalize_st_frame(raw_st)
        prices = prices.merge(st, on=["trade_date", "code"], how="left")
    except Exception as error:
        warnings.append("is_st {}..{} {}: {}".format(start_date, end_date, len(codes), error))
        prices["is_st"] = None

    prices["is_member"] = [
        code in active_by_date.get(trade_date, set())
        for trade_date, code in zip(prices["trade_date"], prices["code"])
    ]
    prices = prices[prices["is_member"]].drop(columns=["is_member"])
    for column in DAILY_COLUMNS:
        if column not in prices.columns:
            prices[column] = None
    return prices[DAILY_COLUMNS]


def write_constituents(path, frame):
    """Write a fresh UTF-8 CSV suitable for Excel and Python."""
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def export_daily(path, codes, trade_days, snapshots, warnings):
    """Write yearly and code-batched daily data without keeping all rows in RAM."""
    active_by_date = active_membership_by_date(snapshots, trade_days)
    if os.path.exists(path):
        os.remove(path)

    wrote_header = False
    total_rows = 0
    ranges = list(date_ranges(date_text(trade_days[0]), date_text(trade_days[-1])))
    for year_start, year_end in ranges:
        print("daily range", year_start, year_end)
        for offset in range(0, len(codes), PRICE_BATCH_SIZE):
            batch = codes[offset : offset + PRICE_BATCH_SIZE]
            frame = fetch_daily_batch(batch, year_start, year_end, active_by_date, warnings)
            if len(frame) == 0:
                continue
            frame = frame.sort_values(["trade_date", "code"])
            frame.to_csv(
                path,
                mode="a",
                header=not wrote_header,
                index=False,
                encoding="utf-8-sig" if not wrote_header else "utf-8",
            )
            wrote_header = True
            total_rows += len(frame)
            print("daily batch", year_start, offset + len(batch), "/", len(codes), "rows", total_rows)

    if not wrote_header:
        pd.DataFrame(columns=DAILY_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")
    return total_rows


def main():
    """Run the JoinQuant export."""
    output_dir = OUTPUT_DIR
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    warnings = []
    trade_days = get_trade_dates()
    snapshots, membership_cache = collect_membership_snapshots(trade_days)
    constituent_frame = build_constituent_rows(snapshots, warnings)

    all_codes = clean_codes(constituent_frame["code"].tolist())
    if TEST_MODE:
        all_codes = all_codes[:TEST_MAX_CODES]

    constituent_path = os.path.join(output_dir, CONSTITUENT_FILENAME)
    daily_path = os.path.join(output_dir, DAILY_FILENAME)
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)

    write_constituents(constituent_path, constituent_frame)
    daily_rows = export_daily(daily_path, all_codes, trade_days, snapshots, warnings)

    manifest = {
        "schema_version": 1,
        "index_code": INDEX_CODE,
        "start_date": date_text(trade_days[0]),
        "end_date": date_text(trade_days[-1]),
        "requested_start_date": START_DATE,
        "requested_end_date": END_DATE,
        "test_mode": TEST_MODE,
        "constituent_snapshot_count": len(snapshots),
        "constituent_row_count": len(constituent_frame),
        "daily_code_count": len(all_codes),
        "daily_row_count": daily_rows,
        "membership_api_cache_count": len(membership_cache),
        "price_batch_size": PRICE_BATCH_SIZE,
        "constituent_probe_days": CONSTITUENT_PROBE_DAYS,
        "files": [CONSTITUENT_FILENAME, DAILY_FILENAME],
        "warnings": warnings,
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    print("EXPORT COMPLETE")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print("Download these files from the JoinQuant research environment:")
    print(constituent_path)
    print(daily_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
