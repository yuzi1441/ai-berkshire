import importlib.util, sys
for mod in ['pdfplumber','pypdf','pandas','akshare','requests','bs4']:
    print(mod, importlib.util.find_spec(mod) is not None)