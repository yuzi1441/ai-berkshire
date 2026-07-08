from bs4 import BeautifulSoup
from pathlib import Path
for name in ['annual','q1']:
 text=Path(f'.tmp_sina_{name}.html').read_text(encoding='utf-8')
 soup=BeautifulSoup(text,'html.parser')
 print('\n',name)
 for a in soup.find_all('a', href=True):
  h=a['href']; t=a.get_text(strip=True)
  if 'PDF' in t or '下载' in t or '公告原文' in t or '.PDF' in h.upper(): print(t,h)
