import importlib.util
mods=['akshare','yfinance','tushare']
for m in mods: print(m, bool(importlib.util.find_spec(m)))