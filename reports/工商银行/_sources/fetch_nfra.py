import requests, re
from bs4 import BeautifulSoup
url='https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1260352&itemId=4113'
r=requests.get(url,timeout=20)
r.encoding=r.apparent_encoding
print(r.status_code, r.encoding)
text=r.text
for pat in ['中国工商','处罚','罚款','银行']:
 print(pat, text.find(pat))
soup=BeautifulSoup(text,'html.parser')
print(soup.get_text('\n', strip=True)[:3000])
