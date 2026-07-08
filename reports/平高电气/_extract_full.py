from pathlib import Path
import pdfplumber
# extract all annual text clean
with pdfplumber.open('_sources/annual_2025.pdf') as pdf:
    text='\n'.join(f'\n===== PAGE {i+1} =====\n'+(p.extract_text() or '') for i,p in enumerate(pdf.pages))
Path('_annual_full_text.txt').write_text(text, encoding='utf-8')
# q1 full text
with pdfplumber.open('_sources/q1_2026.pdf') as pdf:
    q='\n'.join(f'\n===== PAGE {i+1} =====\n'+(p.extract_text() or '') for i,p in enumerate(pdf.pages))
Path('_q1_full_text.txt').write_text(q, encoding='utf-8')
# order
with pdfplumber.open('_sources/order_2025_773m.pdf') as pdf:
    o='\n'.join(p.extract_text() or '' for p in pdf.pages)
Path('_order_2025_text.txt').write_text(o, encoding='utf-8')
print('done')
