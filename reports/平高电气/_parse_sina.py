import requests, re
from bs4 import BeautifulSoup
url='https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12304534&stockid=600312'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
r.encoding='gbk'
soup=BeautifulSoup(r.text,'html.parser')
text=soup.get_text('\n', strip=True)
Path=None
for line in text.splitlines():
    if any(x in line for x in ['中标金额','国家电网','南方电网','亿元','万元','占']):
        print(line)