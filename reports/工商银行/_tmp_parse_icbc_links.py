import requests, re
from bs4 import BeautifulSoup
url='https://www.icbc-ltd.com/ICBCLtd/Investor%20Relations/Financial%20Information/Financial%20Reports/default.htm'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
text=r.content.decode('utf-8','replace')
print(text[:300])
# save
open('_icbc_finreports.html','w',encoding='utf-8').write(text)
soup=BeautifulSoup(text,'html.parser')
for a in soup.find_all('a'):
    t=' '.join(a.get_text(' ',strip=True).split())
    href=a.get('href')
    if href and ('2026' in t or '2025' in t or '2026' in href or '2025' in href or 'Annual' in t or 'First Quarterly' in t):
        print(t, '=>', href)