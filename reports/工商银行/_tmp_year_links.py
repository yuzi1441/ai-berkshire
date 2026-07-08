import requests, re
from bs4 import BeautifulSoup
base='https://www.icbc-ltd.com'
urls=['https://www.icbc-ltd.com/en/column/1228703140703055873.html','https://www.icbc-ltd.com/en/column/1210891251105144833.html']
for url in urls:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 text=r.content.decode('utf-8','replace')
 print('\nPAGE',url,'status',r.status_code,'len',len(text))
 open('_'+url.split('/')[-1], 'w', encoding='utf-8').write(text)
 soup=BeautifulSoup(text,'html.parser')
 for a in soup.find_all('a'):
  t=' '.join(a.get_text(' ',strip=True).split())
  href=a.get('href') or ''
  if t or href:
   print(repr(t),'=>',href)