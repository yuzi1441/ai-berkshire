import requests, re
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12011598&stockid=601126'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
r.encoding='gbk'
print(r.status_code, r.url, r.text[:1000])
for m in re.finditer(r'https?://[^"\']+?(?:PDF|pdf|download[^"\']*)', r.text): print(m.group(0)[:300])
print('links')
for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{0,80})', r.text):
    if '下载' in m.group(2) or 'PDF' in m.group(1).upper(): print(m.groups())