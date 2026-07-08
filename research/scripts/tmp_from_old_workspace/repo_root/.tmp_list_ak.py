import akshare as ak
funcs=[x for x in dir(ak) if 'stock' in x and ('financial' in x or 'individual' in x or 'balance' in x or 'profit' in x or 'cash' in x or 'zh_a' in x)]
print('\n'.join(funcs[:300]))
