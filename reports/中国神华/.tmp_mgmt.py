import pdfplumber, pathlib
buf=[]
for pdf in ['sources/annual2025.pdf','sources/q1_2026.pdf']:
    buf.append('\nPDF '+pdf)
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages, start=1):
            txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            if any(k in txt for k in ['张长岩','董事长','总经理','宋静刚','高级管理人员','董事会']):
                buf.append('\n===== PAGE %s =====\n%s' % (i, txt[:5000]))
path=pathlib.Path('sources/mgmt_pages.txt')
path.write_text('\n'.join(buf),encoding='utf-8')
print(path, path.stat().st_size)
