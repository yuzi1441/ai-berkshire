import akshare as ak
import pandas as pd
symbol='000400'
print('--- spot ---')
try:
    df=ak.stock_zh_a_spot_em()
    row=df[df['代码']==symbol]
    print(row.T.to_string())
except Exception as e:
    print('spot err', repr(e))
print('--- individual info ---')
try:
    info=ak.stock_individual_info_em(symbol=symbol)
    print(info.to_string())
except Exception as e:
    print('info err', repr(e))
print('--- financial analysis indicator ---')
try:
    fin=ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2020')
    print(fin.tail(12).to_string())
except Exception as e:
    print('fin err', repr(e))
print('--- balance sheet / profit / cashflow funcs? ---')
for name in ['stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em']:
    try:
        fn=getattr(ak,name)
        df=fn(symbol=symbol)
        print(name, df.shape, df.columns[:10].tolist())
        print(df.head(3).to_string())
    except Exception as e:
        print(name, 'err', repr(e))
