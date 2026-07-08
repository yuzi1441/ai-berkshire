import requests, re
urls=[
('annual','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12112020&stockid=002028'),
('q1','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12181541&stockid=002028'),
]
for name,url in urls:
    print('\n---',name,url)
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
    print(r.status_code,r.encoding,r.apparent_encoding,len(r.content))
    text=r.content.decode(r.apparent_encoding or 'gb18030','ignore')
    print(text[:1000])
    for pat in ['download', 'PDF', 'cninfo', 'static']:
        print(pat, text.find(pat))
    links=re.findall(r'https?://[^\"\']+', text)
    print('links', links[:20])
    open(f'.tmp_sina_{name}.html','w',encoding='utf-8').write(text)
