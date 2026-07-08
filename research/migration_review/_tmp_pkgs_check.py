import importlib.util
for m in ['akshare','pandas','pdfplumber','requests','bs4']:
    print(m, bool(importlib.util.find_spec(m)))