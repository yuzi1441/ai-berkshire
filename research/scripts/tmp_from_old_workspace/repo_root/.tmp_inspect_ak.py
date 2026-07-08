import akshare as ak, inspect
funcs=['stock_financial_abstract','stock_financial_analysis_indicator','stock_financial_analysis_indicator_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_financial_report_sina','stock_zh_a_spot_em','stock_zh_a_hist']
for f in funcs:
    obj=getattr(ak,f,None)
    if obj:
        print('\n##',f)
        print(inspect.signature(obj))
        print((inspect.getdoc(obj) or '')[:500])
