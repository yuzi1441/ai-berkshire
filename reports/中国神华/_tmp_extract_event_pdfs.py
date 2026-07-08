import pdfplumber, pathlib, re, json
src=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\中国神华\sources')
keywords=['营业收入','归属于本公司股东的净利润','归属于母公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','毛利率','资产负债率','利润分配','每股派发现金红利','现金红利','煤炭销售量','商品煤产量','发电量','铁路运输','总资产','负债合计','股东权益','资本开支','购建固定资产']
for pdf in ['2025_annual.pdf','2026_q1.pdf','2025_dividend.pdf','2026_equity_distribution.pdf','2026_reorg_newshares_apr9.pdf','2026_finance_company_related_jun26.pdf','2026_director_pay_jun27.pdf']:
 path=src/pdf
 out=[]
 with pdfplumber.open(path) as p:
  out.append(f'{pdf} pages={len(p.pages)}')
  for pi,page in enumerate(p.pages, start=1):
   text=page.extract_text() or ''
   compact=re.sub(r'\s+',' ',text)
   hits=[kw for kw in keywords if kw in compact]
   if hits:
    out.append(f'--- page {pi} hits {hits} ---')
    for kw in hits[:8]:
     idx=compact.find(kw)
     out.append(compact[max(0,idx-120):idx+350])
  (src/(pdf+'.key.txt')).write_text('\n'.join(out),encoding='utf-8')
  print(pdf, 'wrote', len('\n'.join(out)))