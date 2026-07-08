import akshare as ak, inspect
for name in ['stock_individual_info_em','stock_financial_analysis_indicator','stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_zh_a_hist','stock_zh_a_spot_em','stock_zh_a_disclosure_report_cninfo']:
    f=getattr(ak,name)
    print('\n---',name,'---')
    print(inspect.signature(f))
    print((inspect.getdoc(f) or '')[:600])
