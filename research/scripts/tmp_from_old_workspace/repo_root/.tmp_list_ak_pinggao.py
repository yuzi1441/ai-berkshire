import akshare as ak
names=[n for n in dir(ak) if 'stock' in n and ('financial' in n or 'indicator' in n or 'em' in n or 'report' in n or 'zh_a' in n)]
for n in sorted(names)[:400]: print(n)
