import importlib.util
for m in ['pdfplumber','pypdf','PyPDF2','pandas','requests','bs4']:
    print(m, bool(importlib.util.find_spec(m)))