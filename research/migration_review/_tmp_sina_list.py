import requests, re
from bs4 import BeautifulSoup
urls=[
'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/601126.phtml',
'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/601126.phtml?ftype=ndbg',
]
for url in urls:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 r.encoding='gbk'
 print('\nURL',url,r.status_code,r.url)
 text=r.text
 for line in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*(?:2026|2025|第一季度|年度报告)[^<]*)</a>',text):
   print(line)