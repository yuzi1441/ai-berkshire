import akshare as ak, inspect
for f in ['stock_notice_report','stock_report_disclosure','stock_individual_notice_report','stock_zh_a_disclosure_report_cninfo','stock_profit_sheet_by_report_em']:
 obj=getattr(ak,f)
 print('\n##',f)
 print(inspect.signature(obj))
 print((inspect.getdoc(obj) or '')[:800])
