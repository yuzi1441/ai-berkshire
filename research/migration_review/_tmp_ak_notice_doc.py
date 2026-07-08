import akshare as ak, inspect
for name in ['stock_notice_report','stock_individual_notice_report','stock_zh_a_disclosure_report_cninfo']:
    fn=getattr(ak,name)
    print('\n###',name)
    print(inspect.signature(fn))
    print((inspect.getdoc(fn) or '')[:1000])
