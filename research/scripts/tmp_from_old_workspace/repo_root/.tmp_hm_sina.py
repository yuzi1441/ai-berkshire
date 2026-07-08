import requests, re, pathlib
s=requests.Session(); s.trust_env=False
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=11972985&stockid=002270'
r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30)
print(r.status_code, r.encoding, r.apparent_encoding, r.headers.get('content-type'), len(r.content))
r.encoding=r.apparent_encoding or 'gb18030'
text=r.text
path=pathlib.Path('reports/华明装备/sources/sina_2025_annual.html'); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding='utf-8')
print(text[:1000])
for m in re.finditer(r'https?://[^\"\']+', text):
    u=m.group(0)
    if 'PDF' in u.upper() or 'download' in u or 'static.cninfo' in u: print('URL',u[:300])
print('pdf refs', re.findall(r'(?:href|src)=["\']([^"\']+)', text)[:20])
