import akshare as ak
funcs=[f for f in dir(ak) if 'stock' in f and ('financial' in f or 'indicator' in f or 'zh_a_spot' in f or 'individual' in f)]
for f in funcs[:100]: print(f)