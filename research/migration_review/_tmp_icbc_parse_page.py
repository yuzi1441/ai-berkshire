from bs4 import BeautifulSoup
import requests,re,urllib.parse
s=requests.Session(); s.trust_env=False
url='https://www.icbc-ltd.com/ICBCLtd/%E6%8A%95%E8%B5%84%E8%80%85%E5%85%B3%E7%B3%BB/%E8%B4%A2%E5%8A%A1%E4%BF%A1%E6%81%AF/%E8%B4%A2%E5%8A%A1%E6%8A%A5%E5%91%8A/'
r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
html=r.text
open('reports/工商银行/_tmp_icbc_reports_page.html','w',encoding='utf-8').write(html)
for kw in ['2025','2026','年度报告','第一季度','季度报告','pdf','PDF','Announce']:
 print(kw, html.find(kw))
soup=BeautifulSoup(html,'html.parser')
for a in soup.find_all('a')[:200]:
 text=a.get_text(' ',strip=True); href=a.get('href')
 if text and any(k in text for k in ['2025','2026','报告','季度','年度']):
  print(text[:120], '=>', urllib.parse.urljoin(url,href or ''))
print('--- all pdf-like links ---')
for a in soup.find_all('a'):
 href=a.get('href') or ''; text=a.get_text(' ',strip=True)
 if '.pdf' in href.lower() or 'download' in href.lower() or 'Announce' in href:
  print(text[:80], urllib.parse.urljoin(url,href))