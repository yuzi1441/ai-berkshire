import akshare as ak, inspect
for f in ['stock_zh_a_disclosure_report_cninfo','stock_individual_notice_report','stock_report_disclosure','stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em']:
 fn=getattr(ak,f)
 print('\n',f,inspect.signature(fn))
 print((fn.__doc__ or '')[:500])
