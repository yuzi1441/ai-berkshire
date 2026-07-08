import akshare as ak
for n in dir(ak):
    if any(k in n.lower() for k in ['notice','report','announcement','ann']):
        if 'stock' in n.lower() or 'ann' in n.lower(): print(n)
