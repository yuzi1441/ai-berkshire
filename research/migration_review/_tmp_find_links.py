import re
for file in ['reports/工商银行/_tmp_1228714343244328961.html.html','reports/工商银行/_tmp_1210891474012143617.html.html']:
 print('\nFILE',file)
 html=open(file,encoding='utf-8').read()
 for kw in ['Announce','pdf','download','202604','202603','2026','一季度','季度','年度报告','报告']:
  print(kw, html.find(kw))
 for m in re.finditer(r'https?://[^\s\"\']+',html):
  u=m.group(0)
  if 'download' in u or '.pdf' in u or 'Announce' in u:
   print(u[:300])
 for m in re.finditer(r'[/\w\-.%]*download[/\w\-.%]*',html,re.I):
  print('REL',m.group(0)[:300])
