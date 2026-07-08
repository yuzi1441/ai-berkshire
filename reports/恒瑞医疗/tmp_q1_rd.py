from pathlib import Path
import pdfplumber
p=Path('source_pdfs/hengrui_2026_q1.pdf')
with pdfplumber.open(str(p)) as pdf:
    txt='\n'.join(page.extract_text() or '' for page in pdf.pages)
idx=txt.find('二、报告期内研发进展')
print(txt[idx:idx+3500])
