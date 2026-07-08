import akshare as ak, inspect
for fn in ['stock_zh_a_spot_em','stock_zh_a_hist','stock_individual_info_em','stock_financial_abstract','stock_financial_analysis_indicator','stock_profit_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_zh_a_disclosure_report_cninfo','stock_report_disclosure','stock_individual_notice_report','stock_dividend_cninfo']:
    obj=getattr(ak,fn,None)
    if obj:
        print('\n###',fn)
        print(inspect.signature(obj))
        doc=(inspect.getdoc(obj) or '')[:500]
        print(doc)
