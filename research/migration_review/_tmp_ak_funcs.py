import akshare as ak
for name in dir(ak):
 if any(s in name.lower() for s in ['cash','flow','report','financial','stock_finance']):
  print(name)
