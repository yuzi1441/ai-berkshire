import importlib.util
for m in ['pdfplumber','pandas','requests','akshare','bs4','lxml']:
    print(m, bool(importlib.util.find_spec(m)))
