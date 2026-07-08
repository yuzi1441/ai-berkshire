from pathlib import Path
import pdfplumber, sys
p=Path('source_pdfs/hengrui_2026_q1.pdf')
with pdfplumber.open(str(p)) as pdf:
    txt='\n'.join(page.extract_text() or '' for page in pdf.pages)
for kw in ['创新药','45.26','61.69','对外许可','7.87','仿制药']:
    print('KW',kw, txt.find(kw))
    idx=txt.find(kw)
    if idx!=-1: print(txt[max(0,idx-300):idx+500])
