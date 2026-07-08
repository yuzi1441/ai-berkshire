import requests,re
from bs4 import BeautifulSoup
url='https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/601088.phtml'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20); r.encoding='gbk'
# print links around bulletin area
for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',r.text,re.S):
 txt=re.sub('<.*?>','',m.group(2)); txt=re.sub(r'\s+',' ',txt).strip()
 href=m.group(1)
 if txt:
  print(txt, href)
