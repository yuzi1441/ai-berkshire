import requests, pathlib
urls={
'annual':'https://stockmc.xueqiu.com/202603/601126_20260324_2K9N.pdf',
'q1':'https://stockmc.xueqiu.com/202604/601126_20260430_8ESA.pdf',
'esg':'https://www.sf-auto.com/upload/UF03/f4f6/1cf22d44dc1d4bc2acc3e1a0acaa233c.pdf'
}
out=pathlib.Path('data/raw/sifang'); out.mkdir(parents=True, exist_ok=True)
for k,u in urls.items():
    p=out/f'{k}.pdf'
    r=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=60)
    print(k,r.status_code,r.headers.get('content-type'),len(r.content))
    p.write_bytes(r.content)
    print(p.resolve())