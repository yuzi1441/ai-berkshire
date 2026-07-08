import requests, re
url='https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/002463/page_type/ndbg.phtml'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.encoding, r.apparent_encoding, r.url)
text=r.content.decode(r.apparent_encoding or 'gbk','ignore')
print(text[:1000])
for m in re.finditer(r'href="([^"]*vCB_AllBulletinDetail[^"]*)"[^>]*>(.*?)</a>', text, re.S):
    print(m.group(2).strip(), m.group(1))
