import akshare as ak, pandas as pd, json
funcs = [
 ('stock_zh_a_spot_em', lambda: ak.stock_zh_a_spot_em()),
 ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol='601398')),
 ('stock_financial_analysis_indicator', lambda: ak.stock_financial_analysis_indicator(symbol='601398')),
 ('stock_profit_sheet_by_report_em', lambda: ak.stock_profit_sheet_by_report_em(symbol='SH601398')),
 ('stock_balance_sheet_by_report_em', lambda: ak.stock_balance_sheet_by_report_em(symbol='SH601398')),
 ('stock_cash_flow_sheet_by_report_em', lambda: ak.stock_cash_flow_sheet_by_report_em(symbol='SH601398')),
]
for name, fn in funcs:
    print('\n###', name)
    try:
        df=fn()
        print(df.shape)
        print(list(df.columns)[:80])
        print(df.head(3).to_string())
    except Exception as e:
        print('ERR', type(e).__name__, e)