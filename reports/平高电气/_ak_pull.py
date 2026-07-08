import akshare as ak
import pandas as pd
code='600312'
print('akshare version ok')
for name, func in [
    ('stock_zh_a_spot_em', lambda: ak.stock_zh_a_spot_em()),
    ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol=code)),
]:
    try:
        df=func()
        print('\n', name, df.shape)
        if name=='stock_zh_a_spot_em':
            row=df[df['代码'].astype(str)==code]
            print(row.to_string(index=False))
        else:
            print(df.to_string(index=False))
    except Exception as e:
        print('ERR', name, type(e).__name__, e)
# financial funcs names
for fn in ['stock_financial_report_sina','stock_financial_abstract','stock_financial_analysis_indicator','stock_balance_sheet_by_report_em','stock_profit_sheet_by_report_em','stock_cash_flow_sheet_by_report_em']:
    print(fn, hasattr(ak, fn))
