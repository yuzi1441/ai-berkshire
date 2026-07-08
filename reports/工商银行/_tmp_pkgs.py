import importlib.util
for m in ['pdfplumber','pypdf','PyPDF2','camelot','tabula']:
 print(m, importlib.util.find_spec(m) is not None)