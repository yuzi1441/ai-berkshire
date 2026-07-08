import akshare as ak, inspect
for name in dir(ak):
 if 'report' in name.lower() and ('cninfo' in name.lower() or 'disclosure' in name.lower() or 'notice' in name.lower()):
  try: sig=str(inspect.signature(getattr(ak,name)))
  except Exception: sig=''
  print(name, sig)