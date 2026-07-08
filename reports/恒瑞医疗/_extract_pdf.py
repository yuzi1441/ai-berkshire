import os, re, pdfplumber, json
base=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs'
out=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\pdf_hits_utf8.txt'
keywords=['孙飘扬','戴洪斌','冯佶','刘健俊','董事、监事和高级管理人员','任职情况','持股变动','薪酬','前十名股东','现金分红','利润分配','股份回购','研发投入','创新药','对外许可','关联交易','非经营性占用','员工','职工','治理']
with open(out,'w',encoding='utf-8') as f:
  for fn in os.listdir(base):
    if not fn.lower().endswith('.pdf'): continue
    path=os.path.join(base,fn)
    f.write(f'\n### {fn}\n')
    with pdfplumber.open(path) as pdf:
      for i,p in enumerate(pdf.pages, start=1):
        txt=p.extract_text() or ''
        hits=[k for k in keywords if k in txt]
        if hits:
          sn=txt[:2500].replace('\n',' | ')
          f.write(f'-- page {i} hits {hits} --\n{sn}\n')
print(out)
