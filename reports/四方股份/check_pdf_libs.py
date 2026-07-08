import importlib.util
for m in ['pdfplumber','pypdf','pandas']:
 print(m, bool(importlib.util.find_spec(m)))
