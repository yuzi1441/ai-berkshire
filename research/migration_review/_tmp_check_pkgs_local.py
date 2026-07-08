import importlib.util
for m in ['akshare','pandas','requests','pdfplumber','bs4']:
    print(m, bool(importlib.util.find_spec(m)))
