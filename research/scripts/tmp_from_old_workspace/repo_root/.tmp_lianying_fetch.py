import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', 200)
pd.set_option('display.width', 240)
code='688271'
sym='SH688271'
print('=== spot ===')
try:
    df=ak.stock_zh_a_spot_em()
    row=df[df['代码'].astype(str)==code]
    print(row.T.to_string())
except Exception as e: print('ERR spot',repr(e))
print('=== indicators ===')
for ind in ['按报告期','按单季度']:
    try:
        df=ak.stock_financial_analysis_indicator_em(symbol=f'{code}.SH', indicator=ind)
        print(ind, df.head(12).to_string())
        df.to_csv(f'data/lianying_indicator_{ind}.csv', index=False, encoding='utf-8-sig')
    except Exception as e: print('ERR ind',ind,repr(e))
print('=== profit ===')
try:
    df=ak.stock_profit_sheet_by_report_em(symbol=sym)
    print(df.head(10).to_string())
    df.to_csv('data/lianying_profit.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR profit',repr(e))
print('=== balance ===')
try:
    df=ak.stock_balance_sheet_by_report_em(symbol=sym)
    print(df.head(10).to_string())
    df.to_csv('data/lianying_balance.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR bal',repr(e))
print('=== cash ===')
try:
    df=ak.stock_cash_flow_sheet_by_report_em(symbol=sym)
    print(df.head(10).to_string())
    df.to_csv('data/lianying_cash.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR cash',repr(e))
print('=== gbjg ===')
try:
    df=ak.stock_zh_a_gbjg_em(symbol=f'{code}.SH')
    print(df.head(20).to_string())
    df.to_csv('data/lianying_gbjg.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR gbjg',repr(e))
print('=== notices cninfo ===')
try:
    df=ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market='沪深京', category='年报', start_date='20260101', end_date='20260706')
    print(df.head(10).to_string())
    df.to_csv('data/lianying_cninfo_annual.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR cninfo annual',repr(e))
try:
    df=ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market='沪深京', category='一季报', start_date='20260101', end_date='20260706')
    print(df.head(10).to_string())
    df.to_csv('data/lianying_cninfo_q1.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR cninfo q1',repr(e))
