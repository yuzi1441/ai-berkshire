import requests, re, pathlib, json, time
ids={
 '2026Q1':'12201904',
 '2025AR':'11972985',
 '2024AR':'10862534',
 '2023AR_summary':'9957449',
}
out=pathlib.Path('reports/华明装备/sources'); out.mkdir(parents=True,exist_ok=True)
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://money.finance.sina.com.cn/'}
meta={}
for name,id_ in ids.items():
    page=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id={id_}&stockid=002270'
    r=s.get(page,headers=headers,timeout=30)
    enc=r.apparent_encoding or 'gb18030'
    html=r.content.decode(enc,'ignore')
    (out/f'sina_{name}_{id_}.html').write_text(html,encoding='utf-8')
    urls=re.findall(r'https?://file\.finance\.sina\.com\.cn/[^"<>\s]+?\.PDF', html)
    meta[name]={'page':page,'urls':urls[:3]}
    print(name, r.status_code, len(html), urls[:1])
    if urls:
        rr=s.get(urls[0],headers=headers,timeout=60)
        print('  pdf',rr.status_code,rr.headers.get('content-type'),len(rr.content))
        (out/f'{name}_{id_}.pdf').write_bytes(rr.content)
    time.sleep(.5)
(out/'sina_download_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
