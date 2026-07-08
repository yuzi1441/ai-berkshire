import pdfplumber, pathlib
path='sources/沪电股份/沪电股份2025年年度报告.pdf'
with pdfplumber.open(path) as pdf:
    pages=[]
    for i,p in enumerate(pdf.pages):
        txt=p.extract_text() or ''
        if any(k in txt for k in ['陈梅芳','吴礼淦','吴传彬','董事长','总经理','高级管理人员','股票期权','激励计划','股份支付','薪酬']):
            pages.append(f'---PAGE {i+1}---\n{txt}')
pathlib.Path('data/ar2025_management_pages.txt').write_text('\n\n'.join(pages),encoding='utf-8')
print([int(x.split('---PAGE ')[1].split('---')[0]) for x in pages])
