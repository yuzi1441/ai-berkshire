import pdfplumber, pathlib, re, json
files={
 'ar2025':'sources/沪电股份/沪电股份2025年年度报告.pdf',
 'q12026':'sources/沪电股份/沪电股份2026年一季度报告.pdf',
 'ar2024':'sources/沪电股份/沪电股份2024年年度报告.pdf',
}
terms=['营业收入','主营业务','分行业','分产品','印制电路板','企业通讯市场板','汽车板','数据中心','人工智能','前五名客户','研发投入','股本','董事长','总经理','风险','行业','毛利率','境外','市场占有率','全球']
for key,path in files.items():
 print('\n###',key,path)
 with pdfplumber.open(path) as pdf:
  print('pages',len(pdf.pages))
  hits=[]
  for i,p in enumerate(pdf.pages):
   txt=p.extract_text() or ''
   if any(t in txt for t in terms):
    # include only first 70 hits relevant
    snippets=[]
    for t in terms:
     idx=txt.find(t)
     if idx!=-1:
      snippets.append(txt[max(0,idx-120):idx+500].replace('\n',' '))
    if snippets:
     hits.append((i+1,snippets[:3]))
  print('hit pages', [h[0] for h in hits[:80]])
  out=[]
  for pg,snips in hits[:80]:
   out.append(f'--- page {pg} ---\n'+'\n'.join(snips))
  pathlib.Path(f'data/{key}_hudian_snippets.txt').write_text('\n\n'.join(out),encoding='utf-8')
  print('\n'.join(out[:8])[:4000])
