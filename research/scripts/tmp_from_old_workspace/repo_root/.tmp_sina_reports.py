import requests, re
for page,url in [('yjdbg','https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/002463/page_type/yjdbg.phtml'),('all','https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/002463.phtml')]:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 text=r.content.decode('gb18030','ignore')
 print('---',page,len(text))
 for m in re.finditer(r"(20\d\d-\d\d-\d\d)&nbsp;<a target='_blank' href='([^']+)'>(.*?)</a>", text):
     title=re.sub('<.*?>','',m.group(3))
     if '2026' in title or '2025' in title or '第一季度' in title:
         print(m.group(1), title, m.group(2))
