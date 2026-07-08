import importlib.util
for m in ['pdfplumber','pypdf','pandas']:
 print(m, importlib.util.find_spec(m) is not None)
