import importlib.util
for p in ['akshare','pandas','requests','pdfplumber','bs4','lxml','openpyxl']:
    print(p, bool(importlib.util.find_spec(p)))
