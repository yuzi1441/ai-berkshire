import requests,re,json
from bs4 import BeautifulSoup
# Try Sina stock bulletin list pages for recent announcements
urls=[
 'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletin.php?stockid=601088',
 'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/601088.phtml',
]
for url in urls:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20); r.encoding='gbk'
 print('\nURL',url,r.status_code,len(r.text),r.text[:80])
 soup=BeautifulSoup(r.text,'html.parser')
 for a in soup.find_all('a',href=True)[:80]:
  txt=a.get_text(' ',strip=True)
  href=a['href']
  if '2026' in txt or '董事' in txt or '高管' in txt or '季度' in txt or '年度' in txt or '分红' in txt or '利润分配' in txt:
   print(txt, href)
