import pathlib, requests
root=pathlib.Path.cwd()
out=root/'sources'/'东方电子'
out.mkdir(parents=True, exist_ok=True)
files={
 '东方电子-2025年年度报告.pdf':'http://static.cninfo.com.cn/finalpage/2026-04-24/1225161855.PDF',
 '东方电子-2026年一季度报告.pdf':'http://static.cninfo.com.cn/finalpage/2026-04-29/1225233627.PDF',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,url in files.items():
    p=out/name
    r=requests.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content))
    r.raise_for_status()
    p.write_bytes(r.content)
    print(p)