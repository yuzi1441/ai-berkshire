import requests, re, pathlib
ids={'annual2025':'12048559','q1_2026':'12188063'}
out=pathlib.Path('sources'); out.mkdir(exist_ok=True)
for name,id in ids.items():
    url=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id={id}&stockid=601088'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30); r.encoding='gbk'
    pdfs=re.findall(r'''https?://[^\"']+?\.PDF|https?://[^\"']+?\.pdf''', r.text)
    print(name, pdfs[:1])
    pr=requests.get(pdfs[0],headers={'User-Agent':'Mozilla/5.0'},timeout=60)
    p=out/f'{name}.pdf'; p.write_bytes(pr.content)
    print(p.resolve(), len(pr.content), pr.content[:4])
