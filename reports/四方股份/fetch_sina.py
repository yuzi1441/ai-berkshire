import requests, re, pathlib
urls=[
'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=601126&id=12011598',
'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=601126&id=12011598',
'https://finance.sina.com.cn/realstock/company/sh601126/nc.shtml'
]
headers={'User-Agent':'Mozilla/5.0'}
for url in urls:
    r=requests.get(url,headers=headers,timeout=30)
    print('\nURL',url, r.status_code, r.headers.get('content-type'), len(r.content))
    enc=r.apparent_encoding
    text=r.content.decode(enc, errors='replace')
    print('enc',enc,'title', re.search(r'<title>(.*?)</title>', text, re.S).group(1)[:100] if re.search(r'<title>(.*?)</title>', text, re.S) else 'none')
    print(text[:500].replace('\n',' ')[:500])
    pathlib.Path('sina_'+re.sub(r'\W+','_',url)[-50:]+'.html').write_text(text,encoding='utf-8')
