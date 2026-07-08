mods=['akshare','pandas','pdfplumber','requests','bs4']
for m in mods:
 try:
  mod=__import__(m); print(m, 'OK', getattr(mod,'__version__',''))
 except Exception as e: print(m,'ERR',repr(e))
