import re, os
for fn in ['_1228703140703055873.html','_1210891251105144833.html']:
 print('\nFILE',fn)
 text=open(fn,encoding='utf-8').read()
 for pat in ['2025 Annual','2026 First','First Quarterly','Quarterly','Annual Report','2025 Results','Announcement','download/2026']:
  print('PAT',pat, [m.start() for m in re.finditer(re.escape(pat), text, re.I)][:10])
 for m in re.finditer(r'(?:href|src)=["\']([^"\']+)["\']', text):
  href=m.group(1)
  if 'download/2026' in href or '.pdf' in href.lower():
   s=max(0,m.start()-200); e=min(len(text),m.end()+200)
   print(text[s:e].replace('\n',' ')[:500])