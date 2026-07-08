import requests, re
from bs4 import BeautifulSoup
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12014866&stockid=002463'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.url, r.encoding, r.apparent_encoding, r.headers.get('content-type'))
text=r.content.decode(r.apparent_encoding or 'gb18030','ignore')
print(text[:1000])
for m in re.finditer(r'https?://[^\'"<>]+\.PDF|https?://[^\'"<>]+\.pdf|href=["\']([^"\']+)', text):
    print(m.group(0)[:300])
