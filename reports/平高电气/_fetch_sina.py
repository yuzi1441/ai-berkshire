import requests, re
url='https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12304534&stockid=600312'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.url, len(r.text), r.encoding)
text=r.text
print(text[:500])
for pat in ['20.92','中标','2026','国家电网','公告']:
    print(pat, text.find(pat))