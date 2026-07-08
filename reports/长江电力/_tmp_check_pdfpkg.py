import importlib.util
print('pdfplumber', importlib.util.find_spec('pdfplumber') is not None)
print('pypdf', importlib.util.find_spec('pypdf') is not None)