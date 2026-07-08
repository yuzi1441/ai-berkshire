import akshare as ak, inspect
funcs=[x for x in dir(ak) if 'stock' in x and ('holder' in x or 'management' in x or 'main' in x or 'profile' in x or 'zygc' in x or 'business' in x or 'share' in x or 'gdfx' in x or 'leader' in x)]
print('\n'.join(funcs[:300]))
for name in funcs[:60]:
 try:
  f=getattr(ak,name); doc=(inspect.getdoc(f) or '').split('\n')[0]
  print(name, inspect.signature(f), doc)
 except Exception as e: pass
