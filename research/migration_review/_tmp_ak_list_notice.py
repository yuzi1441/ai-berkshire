import akshare as ak, inspect
names=[n for n in dir(ak) if 'notice' in n.lower() or 'disclosure' in n.lower() or 'report' in n.lower()]
print('\n'.join(names[:200]))
