import akshare as ak
names=[n for n in dir(ak) if 'stock' in n.lower() and ('financial' in n.lower() or 'profit' in n.lower() or 'balance' in n.lower() or 'cash' in n.lower() or 'indicator' in n.lower())]
for n in names[:300]: print(n)
print('count', len(names))