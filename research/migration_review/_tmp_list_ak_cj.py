import akshare as ak
funcs=[f for f in dir(ak) if 'report' in f.lower() or 'disclosure' in f.lower() or 'financial' in f.lower()]
for f in funcs:
    if any(x in f for x in ['stock','finance']):
        print(f)
