#!/usr/bin/env python3
"""Backtest the previously specified CSI 300 technical strategy.

The input is the point-in-time constituent and daily-bar export created from
JoinQuant. Signals are computed from the close of day t and orders are
attempted at the open of t+1. The script intentionally keeps the official
CSI 300 index benchmark separate because its index OHLC data is not part of
the constituent export.

The default sizing model is conservative equal slots: each of at most 20
slots targets 1/20 of marked portfolio equity. Unused slots remain in cash.
This makes the sizing assumption explicit instead of silently investing all
cash when only a few signals exist.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import talib


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
INDICATOR_COLUMNS = [
    "sma20",
    "sma60",
    "sma200",
    "rsi14",
    "atr14",
    "distance_atr",
    "buy_signal",
    "trend_exit",
]


@dataclass
class Position:
    code: str
    shares: int
    entry_price: float
    entry_atr: float
    entry_date: pd.Timestamp
    entry_signal_date: pd.Timestamp
    entry_cost: float
    last_close: float
    last_seen_date: pd.Timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("local/backtest/hs300"),
        help="Directory containing the JoinQuant CSV export.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("local/backtest/hs300/results"),
    )
    parser.add_argument("--initial-capital", type=float, default=10_000_000.0)
    parser.add_argument("--max-holdings", type=int, default=20)
    parser.add_argument("--commission-bps", type=float, default=2.5)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument(
        "--proxy-exit-on-universe-removal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Close a position at its last valid close when the point-in-time "
            "export stops containing the code. This is flagged as a proxy "
            "event because the next-day open is unavailable."
        ),
    )
    return parser.parse_args()


def load_data(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    manifest = json.loads(
        (data_dir / "hs300_export_manifest.json").read_text(encoding="utf-8")
    )
    constituents = pd.read_csv(
        data_dir / "hs300_constituents_2010_2025.csv",
        dtype={"code": "string"},
    )
    daily = pd.read_csv(
        data_dir / "hs300_daily_2010_2025.csv",
        dtype={"code": "string"},
    )
    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    daily["code"] = daily["code"].astype(str)
    daily = daily.sort_values(["trade_date", "code"]).reset_index(drop=True)
    return constituents, daily, manifest


def audit_data(
    constituents: pd.DataFrame,
    daily: pd.DataFrame,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Return reproducible checks for the point-in-time export."""
    required_constituents = ["effective_date", "code", "weight"]
    required_daily = DAILY_COLUMNS
    effective_dates = np.array(sorted(constituents["effective_date"].dropna().unique()))
    snapshot_members = {
        str(key): set(group["code"].astype(str))
        for key, group in constituents.groupby("effective_date")
    }
    membership_mismatches = 0
    if len(effective_dates):
        snapshot_index = np.searchsorted(
            effective_dates,
            daily["trade_date"].dt.strftime("%Y-%m-%d").to_numpy(),
            side="right",
        ) - 1
        for index, snapshot_index_value in enumerate(snapshot_index):
            if snapshot_index_value < 0:
                membership_mismatches += 1
                continue
            snapshot_date = str(effective_dates[snapshot_index_value])
            if str(daily.iloc[index]["code"]) not in snapshot_members[snapshot_date]:
                membership_mismatches += 1
    return {
        "manifest_test_mode": manifest.get("test_mode"),
        "manifest_warnings": manifest.get("warnings", []),
        "required_constituent_columns_present": all(
            column in constituents.columns for column in required_constituents
        ),
        "required_daily_columns_present": all(
            column in daily.columns for column in required_daily
        ),
        "constituent_rows": int(len(constituents)),
        "constituent_snapshot_count": int(constituents["effective_date"].nunique()),
        "constituent_code_count": int(constituents["code"].nunique()),
        "constituent_duplicate_keys": int(
            constituents.duplicated(["effective_date", "code"]).sum()
        ),
        "constituent_missing_by_column": {
            key: int(value) for key, value in constituents.isna().sum().items()
        },
        "daily_rows": int(len(daily)),
        "daily_trade_date_count": int(daily["trade_date"].nunique()),
        "daily_code_count": int(daily["code"].nunique()),
        "daily_date_min": daily["trade_date"].min().strftime("%Y-%m-%d"),
        "daily_date_max": daily["trade_date"].max().strftime("%Y-%m-%d"),
        "daily_duplicate_keys": int(daily.duplicated(["trade_date", "code"]).sum()),
        "daily_missing_by_column": {
            key: int(value) for key, value in daily.isna().sum().items()
        },
        "point_in_time_membership_mismatch_rows": int(membership_mismatches),
        "note": (
            "Missing OHLCV/paused rows are preserved as non-executable observations; "
            "missing weights are not imputed."
        ),
    }


def add_indicators(daily: pd.DataFrame) -> pd.DataFrame:
    """Calculate indicators on valid trading bars and align them to raw rows."""
    output: list[pd.DataFrame] = []
    for _, group in daily.groupby("code", sort=False):
        group = group.sort_values("trade_date").copy()
        for column in INDICATOR_COLUMNS:
            group[column] = False if column in {"buy_signal", "trend_exit"} else np.nan
        # The export contains rows only while a code is in the index. A long
        # date gap therefore means the code left the point-in-time universe.
        # Reset indicators at that boundary instead of compressing the gap
        # into adjacent technical bars.
        group["segment"] = group["trade_date"].diff().dt.days.gt(20).cumsum()
        for _, segment in group.groupby("segment", sort=False):
            valid = segment[
                ["open", "high", "low", "close", "paused"]
            ].notna().all(axis=1) & segment["paused"].eq(0)
            bars = segment.loc[valid].copy()
            if len(bars) < 200:
                continue
            close = bars["close"].to_numpy(dtype=float)
            high = bars["high"].to_numpy(dtype=float)
            low = bars["low"].to_numpy(dtype=float)
            bars["sma20"] = talib.SMA(close, timeperiod=20)
            bars["sma60"] = talib.SMA(close, timeperiod=60)
            bars["sma200"] = talib.SMA(close, timeperiod=200)
            bars["rsi14"] = talib.RSI(close, timeperiod=14)
            bars["atr14"] = talib.ATR(high, low, close, timeperiod=14)
            bars["sma20_prev"] = bars["sma20"].shift(1)
            bars["sma60_prev"] = bars["sma60"].shift(1)
            bars["distance_atr"] = np.minimum(
                (bars["close"] - bars["sma20"]).abs(),
                (bars["close"] - bars["sma60"]).abs(),
            ) / bars["atr14"].replace(0, np.nan)
            bars["buy_signal"] = (
                (bars["close"] > bars["sma200"])
                & (bars["sma20"] > bars["sma20_prev"])
                & (bars["sma60"] >= bars["sma60_prev"])
                & (bars["distance_atr"] <= 1.0)
                & bars["rsi14"].between(35.0, 65.0)
            )
            bars["trend_exit"] = (
                (bars["close"] < bars["sma200"])
                | (
                    (bars["close"] < bars["sma60"])
                    & (bars["sma60"] < bars["sma60_prev"])
                )
            )
            for column in INDICATOR_COLUMNS:
                group.loc[bars.index, column] = bars[column]
        group = group.drop(columns=["segment"])
        output.append(group)
    return pd.concat(output, ignore_index=True).sort_values(
        ["trade_date", "code"]
    )


def stamp_tax_rate(trade_date: pd.Timestamp) -> float:
    """Historical A-share stamp-tax rates used by the requested model."""
    if trade_date >= pd.Timestamp("2023-08-28"):
        return 0.0005
    return 0.001


def fee_for(gross: float, side: str, trade_date: pd.Timestamp, args: argparse.Namespace) -> float:
    commission = max(gross * args.commission_bps / 10_000.0, args.min_commission)
    stamp = gross * stamp_tax_rate(trade_date) if side == "sell" else 0.0
    return commission + stamp


def row_value(row: pd.Series, name: str) -> float | None:
    value = row.get(name)
    if value is None or pd.isna(value):
        return None
    return float(value)


def can_execute(row: pd.Series | None, side: str) -> bool:
    if row is None:
        return False
    open_price = row_value(row, "open")
    paused = row_value(row, "paused")
    high_limit = row_value(row, "high_limit")
    low_limit = row_value(row, "low_limit")
    if open_price is None or paused is None or paused != 0:
        return False
    if high_limit is None or low_limit is None:
        return False
    tolerance = 1e-9
    if side == "buy" and open_price >= high_limit * (1.0 - tolerance):
        return False
    if side == "sell" and open_price <= low_limit * (1.0 + tolerance):
        return False
    return True


def mark_value(
    positions: dict[str, Position],
    bars: pd.DataFrame | None,
    use_open: bool = False,
) -> tuple[float, int]:
    value = 0.0
    missing = 0
    for code, position in positions.items():
        row = None if bars is None else bars.loc[code] if code in bars.index else None
        field = "open" if use_open else "close"
        price = row_value(row, field) if row is not None else None
        if price is None:
            price = position.last_close
            missing += 1
        value += position.shares * price
    return value, missing


def exit_reason(row: pd.Series, position: Position) -> str | None:
    close = row_value(row, "close")
    sma200 = row_value(row, "sma200")
    sma60 = row_value(row, "sma60")
    sma60_prev = row_value(row, "sma60_prev")
    trend_exit = bool(row.get("trend_exit", False))
    stop_level = position.entry_price - 2.0 * position.entry_atr
    if close is not None and close < stop_level:
        return "atr_stop"
    if trend_exit and sma200 is not None and close is not None and close < sma200:
        return "trend_break"
    if (
        close is not None
        and sma60 is not None
        and sma60_prev is not None
        and close < sma60
        and sma60 < sma60_prev
    ):
        return "sma60_break"
    return None


def execute_buy(
    code: str,
    row: pd.Series,
    signal_date: pd.Timestamp,
    signal_atr: float,
    signal_distance: float,
    target_value: float,
    state: dict[str, Any],
    args: argparse.Namespace,
    trade_date: pd.Timestamp,
) -> bool:
    open_price = row_value(row, "open")
    if open_price is None:
        return False
    execution_price = open_price * (1.0 + args.slippage_bps / 10_000.0)
    lot = args.lot_size
    shares = int(math.floor(target_value / execution_price / lot) * lot)
    while shares > 0:
        gross = shares * execution_price
        fees = fee_for(gross, "buy", trade_date, args)
        if gross + fees <= state["cash"] + 1e-8:
            break
        shares -= lot
    if shares <= 0:
        return False
    gross = shares * execution_price
    fees = fee_for(gross, "buy", trade_date, args)
    state["cash"] -= gross + fees
    position = Position(
        code=code,
        shares=shares,
        entry_price=execution_price,
        entry_atr=signal_atr,
        entry_date=trade_date,
        entry_signal_date=signal_date,
        entry_cost=gross + fees,
        last_close=open_price,
        last_seen_date=trade_date,
    )
    state["positions"][code] = position
    state["trades"].append(
        {
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "code": code,
            "side": "buy",
            "reason": "technical_entry",
            "shares": shares,
            "price": execution_price,
            "gross": gross,
            "fees": fees,
            "signal_date": signal_date.strftime("%Y-%m-%d"),
            "signal_distance_atr": signal_distance,
            "entry_atr": signal_atr,
        }
    )
    return True


def execute_sell(
    code: str,
    row: pd.Series | None,
    reason: str,
    state: dict[str, Any],
    args: argparse.Namespace,
    trade_date: pd.Timestamp,
    proxy: bool = False,
) -> bool:
    position = state["positions"].get(code)
    if position is None:
        return True
    open_price = row_value(row, "open") if row is not None else None
    if open_price is None:
        if not proxy:
            return False
        open_price = position.last_close
    execution_price = open_price * (1.0 - args.slippage_bps / 10_000.0)
    gross = position.shares * execution_price
    fees = fee_for(gross, "sell", trade_date, args)
    net = gross - fees
    state["cash"] += net
    trade_return = (net - position.entry_cost) / position.entry_cost
    state["trades"].append(
        {
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "code": code,
            "side": "sell",
            "reason": reason,
            "shares": position.shares,
            "price": execution_price,
            "gross": gross,
            "fees": fees,
            "entry_date": position.entry_date.strftime("%Y-%m-%d"),
            "entry_price": position.entry_price,
            "trade_return_pct": trade_return * 100.0,
            "proxy_exit": proxy,
        }
    )
    if proxy:
        state["proxy_exit_count"] += 1
    state["positions"].pop(code, None)
    return True


def build_candidates(data: pd.DataFrame) -> dict[pd.Timestamp, list[tuple[str, float, float]]]:
    signals = data[data["buy_signal"]].copy()
    signals = signals.dropna(subset=["atr14", "distance_atr"])
    signals = signals.sort_values(["trade_date", "distance_atr", "code"])
    candidates: dict[pd.Timestamp, list[tuple[str, float, float]]] = {}
    for trade_date, group in signals.groupby("trade_date", sort=False):
        candidates[trade_date] = [
            (str(row.code), float(row.distance_atr), float(row.atr14))
            for row in group.itertuples()
        ]
    return candidates


def build_daily_proxy(data: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    """Build an explicitly labelled equal-weight active-universe proxy."""
    valid = data.dropna(subset=["close", "pre_close"])
    valid = valid[(valid["pre_close"] > 0) & valid["paused"].eq(0)].copy()
    valid["return"] = valid["close"] / valid["pre_close"] - 1.0
    returns = valid.groupby("trade_date")["return"].mean().sort_index()
    values = initial_capital * (1.0 + returns).cumprod()
    return pd.DataFrame({"trade_date": values.index, "portfolio_value": values.values})


def performance_metrics(
    curve: pd.DataFrame,
    trades: list[dict[str, Any]],
    initial_capital: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = curve["portfolio_value"].astype(float)
    daily_returns = values.pct_change().dropna()
    total_return = values.iloc[-1] / initial_capital - 1.0
    years = max((end_date - start_date).days / 365.25, 1.0 / 365.25)
    cagr = (values.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    volatility = float(daily_returns.std(ddof=1) * math.sqrt(252)) if len(daily_returns) > 1 else 0.0
    sharpe = (
        float(daily_returns.mean() / daily_returns.std(ddof=1) * math.sqrt(252))
        if len(daily_returns) > 1 and daily_returns.std(ddof=1) > 0
        else None
    )
    drawdown = values / values.cummax() - 1.0
    closed = [trade for trade in trades if trade.get("side") == "sell"]
    winners = [trade for trade in closed if trade.get("trade_return_pct", 0.0) > 0]
    result: dict[str, Any] = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "initial_capital": initial_capital,
        "ending_value": float(values.iloc[-1]),
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "annualized_volatility_pct": volatility * 100.0,
        "sharpe_rf0": sharpe,
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "closed_trade_count": len(closed),
        "trade_win_rate_pct": (len(winners) / len(closed) * 100.0) if closed else None,
        "total_fees": float(sum(float(trade.get("fees", 0.0)) for trade in trades)),
        "total_turnover": float(sum(float(trade.get("gross", 0.0)) for trade in trades)),
    }
    if extra:
        result.update(extra)
    return result


def run_backtest(
    data: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    dates = sorted(data["trade_date"].drop_duplicates())
    date_bars = {
        trade_date: group.set_index("code")
        for trade_date, group in data.groupby("trade_date", sort=False)
    }
    candidates = build_candidates(data)
    state: dict[str, Any] = {
        "cash": float(args.initial_capital),
        "positions": {},
        "trades": [],
        "proxy_exit_count": 0,
        "blocked_order_attempts": 0,
        "missing_mark_days": 0,
    }
    pending_buys: dict[str, dict[str, Any]] = {}
    pending_sells: dict[str, str] = {}
    curve_rows: list[dict[str, Any]] = []

    for index, trade_date in enumerate(dates):
        bars = date_bars[trade_date]

        # Sell orders execute before buys, so a slot released at the open can
        # be reused only after the exit is actually filled.
        for code in list(pending_sells):
            position = state["positions"].get(code)
            if position is None:
                pending_sells.pop(code, None)
                continue
            row = bars.loc[code] if code in bars.index else None
            if row is None:
                if args.proxy_exit_on_universe_removal:
                    execute_sell(
                        code,
                        None,
                        "member_data_ended_proxy",
                        state,
                        args,
                        trade_date,
                        proxy=True,
                    )
                    pending_sells.pop(code, None)
                continue
            if can_execute(row, "sell"):
                execute_sell(
                    code,
                    row,
                    pending_sells[code],
                    state,
                    args,
                    trade_date,
                )
                pending_sells.pop(code, None)
            else:
                state["blocked_order_attempts"] += 1

        # Use the current open to determine the value of one equal slot.
        marked, _ = mark_value(state["positions"], bars, use_open=True)
        open_equity = state["cash"] + marked
        target_slot_value = open_equity / args.max_holdings
        for code in sorted(
            pending_buys,
            key=lambda item: (
                pending_buys[item]["distance_atr"],
                item,
            ),
        ):
            if len(state["positions"]) >= args.max_holdings:
                break
            order = pending_buys[code]
            row = bars.loc[code] if code in bars.index else None
            if row is None:
                pending_buys.pop(code, None)
                continue
            if can_execute(row, "buy"):
                filled = execute_buy(
                    code,
                    row,
                    order["signal_date"],
                    order["atr14"],
                    order["distance_atr"],
                    target_slot_value,
                    state,
                    args,
                    trade_date,
                )
                if filled:
                    pending_buys.pop(code, None)
            else:
                state["blocked_order_attempts"] += 1

        # Update last valid marks and evaluate close-based exits.
        for code, position in list(state["positions"].items()):
            row = bars.loc[code] if code in bars.index else None
            close = row_value(row, "close") if row is not None else None
            if close is not None:
                position.last_close = close
                position.last_seen_date = trade_date
            if row is not None:
                reason = exit_reason(row, position)
                if reason is not None:
                    pending_sells.setdefault(code, reason)

        # Existing pending orders are valid only while their close signal is
        # still present. A blocked order therefore does not live forever.
        for code in list(pending_buys):
            row = bars.loc[code] if code in bars.index else None
            if row is None or not bool(row.get("buy_signal", False)):
                pending_buys.pop(code, None)
        for code in list(pending_sells):
            row = bars.loc[code] if code in bars.index else None
            position = state["positions"].get(code)
            if position is None:
                pending_sells.pop(code, None)
            elif row is not None and exit_reason(row, position) is None:
                pending_sells.pop(code, None)

        # Rank new signals by normalized distance to SMA20/SMA60 and fill
        # available slots at the next open.
        for code, distance_atr, atr14 in candidates.get(trade_date, []):
            if len(state["positions"]) + len(pending_buys) >= args.max_holdings:
                break
            if code in state["positions"] or code in pending_buys or code in pending_sells:
                continue
            pending_buys[code] = {
                "signal_date": trade_date,
                "distance_atr": distance_atr,
                "atr14": atr14,
            }

        close_value, missing_marks = mark_value(state["positions"], bars, use_open=False)
        state["missing_mark_days"] += missing_marks
        curve_rows.append(
            {
                "trade_date": trade_date,
                "portfolio_value": state["cash"] + close_value,
                "cash": state["cash"],
                "positions": len(state["positions"]),
                "pending_buys": len(pending_buys),
                "pending_sells": len(pending_sells),
                "missing_marks": missing_marks,
                "proxy_exit_count": state["proxy_exit_count"],
            }
        )

    curve = pd.DataFrame(curve_rows)
    curve["trade_date"] = pd.to_datetime(curve["trade_date"])
    trades = pd.DataFrame(state["trades"])
    metrics = performance_metrics(
        curve,
        state["trades"],
        args.initial_capital,
        dates[0],
        dates[-1],
        extra={
            "strategy": "hs300_technical_equal_slots",
            "max_holdings": args.max_holdings,
            "commission_bps": args.commission_bps,
            "min_commission": args.min_commission,
            "slippage_bps_each_side": args.slippage_bps,
            "proxy_exit_on_universe_removal": args.proxy_exit_on_universe_removal,
            "proxy_exit_count": state["proxy_exit_count"],
            "blocked_order_attempts": state["blocked_order_attempts"],
            "missing_mark_observations": state["missing_mark_days"],
            "official_index_benchmark": "unavailable: index OHLC was not exported",
            "signal_count": int(data["buy_signal"].sum()),
            "indicator_ready_rows": int(data["sma200"].notna().sum()),
        },
    )
    return metrics, curve, trades


def write_summary(
    output_dir: Path,
    metrics: dict[str, Any],
    proxy_metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    lines = [
        "# CSI 300 technical backtest",
        "",
        "This result uses point-in-time constituent stock data and next-day open execution.",
        "The official CSI 300 index benchmark is not included because index OHLC data was not exported.",
        "",
        "## Strategy metrics",
    ]
    for key in [
        "start_date",
        "end_date",
        "ending_value",
        "total_return_pct",
        "cagr_pct",
        "annualized_volatility_pct",
        "sharpe_rf0",
        "max_drawdown_pct",
        "closed_trade_count",
        "trade_win_rate_pct",
        "proxy_exit_count",
        "blocked_order_attempts",
        "missing_mark_observations",
    ]:
        lines.append(f"- {key}: {metrics.get(key)}")
    lines.extend(
        [
            "",
            "## Available-data proxy",
            "This is an equal-weight average of valid point-in-time constituent close-to-close returns, not the official CSI 300 index.",
        ]
    )
    for key in ["ending_value", "total_return_pct", "cagr_pct", "max_drawdown_pct"]:
        lines.append(f"- {key}: {proxy_metrics.get(key)}")
    lines.extend(
        [
            "",
            "## Export manifest",
            f"- test_mode: {manifest.get('test_mode')}",
            f"- constituent_snapshot_count: {manifest.get('constituent_snapshot_count')}",
            f"- constituent_row_count: {manifest.get('constituent_row_count')}",
            f"- daily_row_count: {manifest.get('daily_row_count')}",
        ]
    )
    (output_dir / "hs300_strategy_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    constituents, daily, manifest = load_data(args.data_dir)
    data_audit = audit_data(constituents, daily, manifest)
    (args.output_dir / "hs300_data_audit.json").write_text(
        json.dumps(data_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    daily = add_indicators(daily)
    metrics, curve, trades = run_backtest(daily, args)
    proxy_curve = build_daily_proxy(daily, args.initial_capital)
    proxy_metrics = performance_metrics(
        proxy_curve,
        [],
        args.initial_capital,
        proxy_curve["trade_date"].iloc[0],
        proxy_curve["trade_date"].iloc[-1],
        extra={"strategy": "equal_weight_active_universe_proxy"},
    )
    (args.output_dir / "hs300_strategy_metrics.json").write_text(
        json.dumps(
            {
                "strategy": metrics,
                "available_data_proxy": proxy_metrics,
                "data_audit": data_audit,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    curve.to_csv(args.output_dir / "hs300_strategy_equity.csv", index=False)
    if len(trades):
        trades.to_csv(args.output_dir / "hs300_strategy_trades.csv", index=False)
    else:
        pd.DataFrame().to_csv(args.output_dir / "hs300_strategy_trades.csv", index=False)
    write_summary(args.output_dir, metrics, proxy_metrics, manifest)
    print(json.dumps({"strategy": metrics, "available_data_proxy": proxy_metrics}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
