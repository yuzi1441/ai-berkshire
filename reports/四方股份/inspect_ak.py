import akshare as ak, inspect
for fn in ['stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_zh_a_disclosure_report_cninfo','stock_notice_report','stock_individual_notice_report']:
    f=getattr(ak,fn)
    print('\n',fn)
    print(inspect.signature(f))
    print((f.__doc__ or '')[:500])
