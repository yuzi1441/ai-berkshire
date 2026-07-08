import importlib.util
for m in ['akshare','tushare','efinance','pandas']:
 print(m, importlib.util.find_spec(m) is not None)