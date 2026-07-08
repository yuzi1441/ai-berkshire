import importlib.util
mods=['akshare','pandas','requests','bs4','pdfplumber','pypdf']
for m in mods:
    print(m, importlib.util.find_spec(m) is not None)
