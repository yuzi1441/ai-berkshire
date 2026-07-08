import importlib.util
for m in ['pdfplumber','pypdf','pandas','requests']:
    print(m, importlib.util.find_spec(m) is not None)
