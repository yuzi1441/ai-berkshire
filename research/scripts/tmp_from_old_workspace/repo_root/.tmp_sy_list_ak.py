import akshare as ak
names=[n for n in dir(ak) if 'stock' in n and ('financial' in n or 'finance' in n or 'indicator' in n or 'zh_a' in n or 'individual' in n)]
for n in sorted(names)[:300]: print(n)
