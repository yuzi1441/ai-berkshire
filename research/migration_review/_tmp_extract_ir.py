from pathlib import Path
import pdfplumber
pdf=Path('source_docs/pgdq/ir_2025_2026q1_20260424.pdf')
out=pdf.with_suffix('.txt')
texts=[]
with pdfplumber.open(str(pdf)) as p:
    for i,page in enumerate(p.pages,1):
        texts.append(f'\n\n--- page {i} ---\n'+(page.extract_text(x_tolerance=1, y_tolerance=3) or ''))
out.write_text('\n'.join(texts),encoding='utf-8')
print(out,out.stat().st_size)
