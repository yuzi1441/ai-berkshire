import akshare as ak
names=[n for n in dir(ak) if ('financial' in n.lower() or 'report' in n.lower() or 'cash' in n.lower() or 'profit' in n.lower()) and ('stock' in n.lower())]
for n in sorted(names): print(n)
