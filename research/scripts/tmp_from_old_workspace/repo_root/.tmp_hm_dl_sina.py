import requests, pathlib, re, time
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}
out=pathlib.Path('reports/华明装备/sources'); out.mkdir(parents=True,exist_ok=True)
# search sina bulletin pages for annual/q1 via known endpoint list? Use all bulletins page parse
for year_id, stockid, name in [('11972985','002270','2025年年度报告')]:
    page=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id={year_id}&stockid={stockid}'
    html=s.get(page,headers=headers,timeout=30).content.decode('gb18030','ignore')
    urls=re.findall(r'https?://file\.finance\.sina\.com\.cn/[^"<>\s]+?\.PDF', html)
    print(name, urls[:2])
    if urls:
        r=s.get(urls[0],headers=headers,timeout=60)
        print('pdf',r.status_code,r.headers.get('content-type'),len(r.content))
        (out/(name+'-sina.pdf')).write_bytes(r.content)
