from bs4 import BeautifulSoup
import requests, urllib.parse, re
s=requests.Session(); s.trust_env=False
url='https://www.icbc-ltd.com/ICBCLtd/%E6%8A%95%E8%B5%84%E8%80%85%E5%85%B3%E7%B3%BB/%E8%B4%A2%E5%8A%A1%E4%BF%A1%E6%81%AF/%E8%B4%A2%E5%8A%A1%E6%8A%A5%E5%91%8A/'
r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print('requests encoding',r.encoding)
for enc in ['utf-8','gbk','gb2312','big5']:
 html=r.content.decode(enc,errors='replace')
 print('\nENC',enc,'年度报告',html.find('年度报告'),'2025',html.find('2025'))
 soup=BeautifulSoup(html,'html.parser')
 n=0
 for a in soup.find_all('a'):
  text=a.get_text(' ',strip=True); href=a.get('href') or ''
  if text and any(k in text for k in ['2025','2026','年度','季度','报告']):
   print(text[:120], '=>', urllib.parse.urljoin(url,href))
   n+=1
   if n>20: break