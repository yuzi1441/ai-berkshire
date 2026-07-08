from pathlib import Path
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
p=Path('source_pdfs/cninfo_recent/1782403200000_1225388513_恒瑞医药关于获得药品注册批准的公告.pdf')
with pdfplumber.open(str(p)) as pdf:
    txt='\n'.join(page.extract_text() or '' for page in pdf.pages)
print(txt[:3500].replace('\n',' '))
