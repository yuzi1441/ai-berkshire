import requests
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12081234&stockid=000400'
r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
print(r.status_code, r.encoding, r.apparent_encoding, len(r.content))
print(r.text[:200].encode('utf-8','ignore'))
open('sina_xj_2025.html','wb').write(r.content)