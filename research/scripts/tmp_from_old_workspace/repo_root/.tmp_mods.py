mods=['akshare','pandas','requests','bs4','pdfplumber','yfinance']
for m in mods:
    try:
        __import__(m); print(m,'OK')
    except Exception as e: print(m,'NO',e)