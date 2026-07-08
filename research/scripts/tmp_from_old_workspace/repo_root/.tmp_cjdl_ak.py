import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', 80)
pd.set_option('display.width', 200)
for name in ['stock_individual_info_em','stock_zh_a_spot_em','stock_financial_abstract_ths','stock_financial_analysis_indicator','stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_history_dividend_detail']:
    print('\nFUNC', name, hasattr(ak, name))
try:
    print('\nindividual')
    print(ak.stock_individual_info_em(symbol='600900'))
except Exception as e: print('ERR individual',repr(e))
try:
    spot=ak.stock_zh_a_spot_em()
    print('\nspot row')
    print(spot[spot['代码']=='600900'].T)
except Exception as e: print('ERR spot',repr(e))
try:
    print('\nindicator')
    df=ak.stock_financial_analysis_indicator(symbol='600900')
    print(df.tail(10).to_string())
except Exception as e: print('ERR indicator',repr(e))
