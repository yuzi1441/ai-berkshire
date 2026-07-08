import akshare as ak
for name in dir(ak):
    if 'report' in name.lower() and ('stock' in name.lower() or 'notice' in name.lower()):
        print(name)