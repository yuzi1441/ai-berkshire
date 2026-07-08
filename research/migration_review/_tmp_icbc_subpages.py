from bs4 import BeautifulSoup
import requests, urllib.parse, re
s=requests.Session(); s.trust_env=False
urls=['https://www.icbc-ltd.com/column/1228714343244328961.html','https://www.icbc-ltd.com/column/1210891474012143617.html']
for url in urls:
 r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 html=r.content.decode('utf-8',errors='replace')
 print('\nURL',url,'status',r.status_code,'len',len(html))
 open('reports/工商银行/_tmp_'+url.split('/')[-1]+'.html','w',encoding='utf-8').write(html)
 soup=BeautifulSoup(html,'html.parser')
 for a in soup.find_all('a'):
  text=a.get_text(' ',strip=True); href=a.get('href') or ''
  if any(k in text for k in ['报告','季度','年度','2025','2026','PDF','下载']) or '.pdf' in href.lower() or 'download' in href.lower() or 'Announce' in href:
   print(text[:120], '=>', urllib.parse.urljoin(url,href))