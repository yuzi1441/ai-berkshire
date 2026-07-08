import requests, re
from bs4 import BeautifulSoup
q='中国神华 2026 年第一季度报告 601088'
url='https://www.bing.com/search?q='+requests.utils.quote(q)
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.url, len(r.text), r.text[:80])
soup=BeautifulSoup(r.text,'html.parser')
for li in soup.select('li.b_algo')[:10]:
    a=li.find('a')
    if a:
        print(a.get_text(' ',strip=True), a.get('href'))
        p=li.get_text(' ',strip=True)
        print(p[:300])
