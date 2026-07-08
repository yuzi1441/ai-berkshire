import requests, re
for url in ['https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12249293&stockid=688271','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12249291&stockid=688271']:
    r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
    print(url, r.status_code, r.encoding, r.apparent_encoding, r.url, len(r.content))
    text=r.content.decode(r.apparent_encoding or 'gb18030', errors='replace')
    print(text[:500])
    print(re.findall(r'https?://[^"\']+?\.pdf[^"\']*', text)[:5])
