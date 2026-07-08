import akshare as ak, pandas as pd
funcs=[f for f in dir(ak) if 'stock_financial' in f or 'financial' in f or 'bank' in f]
for f in funcs[:200]: print(f)