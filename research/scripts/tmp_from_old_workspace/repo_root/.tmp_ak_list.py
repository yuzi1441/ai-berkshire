import akshare as ak
names=[n for n in dir(ak) if 'financial' in n.lower() or 'finance' in n.lower() or 'report' in n.lower()]
for n in names[:300]: print(n)
print('count',len(names))
