import requests, re
url='https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/002463/page_type/ndbg.phtml'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
text=r.content.decode('gb18030','ignore')
open('_tmp_sina_hudian.html','w',encoding='utf-8').write(text)
print(len(text))
for pat in ['2025','年度报告','AllBulletin','bulletin','年报']:
 print(pat, text.find(pat))
