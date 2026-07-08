import requests
from pathlib import Path
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=10181572&stockid=000400'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code,len(r.content),r.encoding,r.apparent_encoding)
text=r.content.decode('gbk','ignore')
Path('xj_2024_regulatory_sina.html').write_text(text,encoding='utf-8')
from bs4 import BeautifulSoup
plain=BeautifulSoup(text,'html.parser').get_text('\n')
Path('xj_2024_regulatory_sina.txt').write_text(plain,encoding='utf-8')
print(plain[plain.find('公司及相关人员'):plain.find('公司及相关人员')+3000])