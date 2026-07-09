import requests, re, pathlib
base=pathlib.Path('research/source_docs/中航机载'); base.mkdir(parents=True, exist_ok=True)
for page,name in [('https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12207677&stockid=600372','q1_2026_sina')]:
    r=requests.get(page,headers={'User-Agent':'Mozilla/5.0'},timeout=30)
    print('page', r.status_code, r.url, r.encoding, len(r.content))
    text=r.content.decode('gbk','ignore')
    print(text[:300])
    pdfs=re.findall(r'https?://[^\"\']+?\.PDF|https?://[^\"\']+?\.pdf', text, re.I)
    print('pdfs', pdfs[:5])
    if pdfs:
        pr=requests.get(pdfs[0],headers={'User-Agent':'Mozilla/5.0'},timeout=60)
        out=base/(name+'.pdf')
        out.write_bytes(pr.content)
        print('saved', out, pr.status_code, pr.headers.get('content-type'), len(pr.content))