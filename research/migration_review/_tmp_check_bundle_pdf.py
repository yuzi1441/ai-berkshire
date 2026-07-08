import sys
print(sys.executable)
for m in ['fitz','pdfplumber','pypdf']:
    try:
        __import__(m); print(m,'ok')
    except Exception as e: print(m,'err',e)
