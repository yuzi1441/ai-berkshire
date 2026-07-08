import akshare as ak, inspect
for n in dir(ak):
    if 'dividend' in n.lower() or 'fhps' in n.lower() or 'fenhong' in n.lower() or 'share_bonus' in n.lower():
        print(n, inspect.signature(getattr(ak,n)))
