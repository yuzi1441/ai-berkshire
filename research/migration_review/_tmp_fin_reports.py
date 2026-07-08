from bs4 import BeautifulSoup
import requests,urllib.parse,re
s=requests.Session(); s.trust_env=False
url='https://www.icbc-ltd.com/column/1438058343653851145.html'
r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
html=r.content.decode('utf-8',errors='replace')
open('reports/工商银行/_tmp_fin_reports.html','w',encoding='utf-8').write(html)
print('status',r.status_code,'len',len(html),'find report',html.find('年度报告'),html.find('2025'),html.find('pdf'))
soup=BeautifulSoup(html,'html.parser')
for a in soup.find_all('a'):
 text=a.get_text(' ',strip=True); href=a.get('href') or ''
 if any(k in text for k in ['2025','2026','年度','季度','报告','半年']) or any(k in href.lower() for k in ['pdf','download','announce','2026']):
  print(text[:150], '=>', urllib.parse.urljoin(url,href))