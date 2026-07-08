import akshare as ak, pandas as pd
funcs=[x for x in dir(ak) if 'stock_financial' in x or 'zh_a' in x and 'spot' in x]
for x in funcs:
 print(x)