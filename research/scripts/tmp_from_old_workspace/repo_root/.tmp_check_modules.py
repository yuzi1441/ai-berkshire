import importlib.util
for m in ['requests','pandas','akshare','pdfplumber','bs4']:
    print(m, bool(importlib.util.find_spec(m)))
