import pdfplumber, pathlib, re
src=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\中国神华\sources')
path=src/'2025_annual.pdf'
terms=['资本性支出总额','资本性支出','报告期投入金额','购建固定资产','现金流量表']
with pdfplumber.open(path) as p:
 for i,page in enumerate(p.pages, start=1):
  text=page.extract_text() or ''
  if any(t in text for t in terms):
   if any(t in text for t in ['资本性支出','购建固定资产']):
    print('PAGE',i)
    compact=re.sub(r'\s+',' ',text)
    for t in terms:
     idx=compact.find(t)
     if idx!=-1: print(t, compact[max(0,idx-200):idx+500])