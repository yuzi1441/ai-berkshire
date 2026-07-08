import akshare as ak, inspect
fn=ak.stock_zh_a_disclosure_report_cninfo
print(fn.__module__)
print(inspect.getsource(fn)[:5000])
