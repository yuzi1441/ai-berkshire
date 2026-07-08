import requests,re
from bs4 import BeautifulSoup
s=requests.Session(); s.trust_env=False
urls=['https://www.icbc-ltd.com/ICBCLtd/Investor%20Relations/Financial%20Information/Financial%20Reports/','https://www.icbc-ltd.com/icbcltd/investor%20relations/financial%20information/financial%20reports/','https://www.icbc-ltd.com/ICBCLtd/%E6%8A%95%E8%B5%84%E8%80%85%E5%85%B3%E7%B3%BB/%E8%B4%A2%E5%8A%A1%E4%BF%A1%E6%81%AF/%E8%B4%A2%E5%8A%A1%E6%8A%A5%E5%91%8A/']
for url in urls:
 try:
  r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
  print('\nURL',url,'status',r.status_code,'len',len(r.content),r.url)
  txt=r.text
  print(txt[:200])
  for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)',txt,re.I):
   href=m.group(1)
   if '2026' in href or '2025' in href or 'Announce' in href:
    print('PDF',href[:200])
 except Exception as e: print('ERR',e)