import re, pathlib
text=pathlib.Path('sources/2025AR_11972985.pdf.txt').read_text(encoding='utf-8',errors='ignore')
patterns=['直接下游','最终用户','深度绑定','全生命周期','运维检修','前五名客户','客户','竞争','售后','海外','特高压','工信部','CNAS','转换']
for p in patterns:
 print('\n###',p)
 for m in list(re.finditer(p,text))[:8]:
  s=max(0,m.start()-180); e=min(len(text),m.end()+260)
  print(text[s:e].replace('\n',' ')[:800])
