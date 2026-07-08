from bs4 import BeautifulSoup
import requests, urllib.parse, re
s=requests.Session(); s.trust_env=False
for url in ['https://www.icbc-ltd.com/ICBCLtd/Investor%20Relations/Financial%20Information/Financial%20Reports/2025/','https://www.icbc-ltd.com/ICBCLtd/Investor%20Relations/Financial%20Information/Financial%20Reports/2025/Annual%20Report/','https://www.icbc-ltd.com/column/1210891474012143617.html']:
 r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 html=r.content.decode('utf-8',errors='replace')
 print('\nURL',url,'status',r.status_code,'len',len(html),'final',r.url)
 soup=BeautifulSoup(html,'html.parser')
 for a in soup.find_all('a'):
  text=a.get_text(' ',strip=True); href=a.get('href') or ''
  if any(k.lower() in (text+' '+href).lower() for k in ['annual','report','2025','pdf','download','interim','quarterly','results']):
   print(text[:100], '=>', urllib.parse.urljoin(url,href))