# Tencent market-data snapshot (2026-07-22)

- Capture window: 2026-07-23 10:59-11:02 HKT (2026-07-23 02:59-03:02 UTC)
- Report trade-date cutoff: 2026-07-22 HKEX close
- Purpose: preserve the values used in `reports/腾讯/腾讯控股研究报告-20260722.md` after dynamic provider pages change.

## 0700.HK price

Yahoo chart endpoint:

`https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?period1=1784505600&period2=1784851200&interval=1d&events=history`

The response identifies the exchange timezone as `Asia/Hong_Kong` (`HKT`). Relevant rows:

| Trade date | Open | High | Low | Close | Volume |
|---|---:|---:|---:|---:|---:|
| 2026-07-21 | 478.20 | 482.60 | 472.80 | 474.00 | 21,362,780 |
| 2026-07-22 | 468.00 | 468.00 | 440.60 | 440.60 | 66,379,871 |

Exact Yahoo close in the JSON was `440.6000061035156`; the report uses the exchange tick value `HK$440.60`. The direct close-to-close change is `(440.60 / 474.00) - 1 = -7.0464%`.

Independent historical-page check:

- Investing.com listed 2026-07-22 close `HK$440.60`, open `HK$468.00`, high `HK$468.00`, low `HK$440.60`, volume `66.38M`, and change `-7.05%`.
- URL: `https://www.investing.com/equities/tencent-holdings-hk-historical-data`

## HKD/CNY conversion

Yahoo chart endpoint:

`https://query1.finance.yahoo.com/v8/finance/chart/HKDCNY=X?period1=1784505600&period2=1784851200&interval=1d&events=history`

- 2026-07-22 close: `0.8627780079841614 CNY/HKD`
- This closing mid-market value is the report's conversion rate.

HKAB historical API:

`https://www.hkab.org.hk/api/member/public/getExrate/2026-07-22`

- `RateDate`: `2026-07-22`
- `CNYSelling`: `117.15` HKD per CNY 100
- `CNYBuyingTT`: `114.65` HKD per CNY 100
- Counter-spread midpoint converted to CNY/HKD: `100 / ((117.15 + 114.65) / 2) = 0.8628127696289905`
- Direct difference from Yahoo close: `0.004029%`

HKAB's buying and selling rates are customer counter rates, not a market close. Their midpoint is used only as an independent reasonableness check.

## Issued shares

Tencent's 2026-07-09 HKEX next-day disclosure reports:

- Issued shares excluding treasury shares: `9,092,516,289`
- Treasury shares: `0`
- Shares repurchased for cancellation but not yet cancelled remain in issued shares until cancellation.
- URL: `https://static.www.tencent.com/uploads/2026/07/09/6438e0c0cb4954c7cfdf88d907716072.pdf`

The Yahoo profile connector returned `9,001,629,075` shares without a comparable as-of date. The direct difference is `90,887,214` shares, or `0.9996%` of the HKEX figure. It is retained as an unresolved timing/definition difference, not treated as an independent confirmation of statutory shares.

## Yahoo peer-profile snapshot

Captured around 2026-07-23 10:59 HKT. These are dynamic, single-provider consensus metrics and are used only for relative context.

| Ticker | Forward PE | Price/book |
|---|---:|---:|
| 0700.HK | 13.739629 | 3.100712 |
| 9988.HK | 14.105054 | 1.7241884 |
| 9999.HK | 13.462655 | 3.2115135 |
| META.US | 16.945055 | 6.532136 |

The same 0700.HK profile response returned `sharesOutstanding = 9,001,629,075`; it did not expose an as-of date for that field.
