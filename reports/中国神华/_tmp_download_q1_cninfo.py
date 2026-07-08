import requests, pathlib
url='https://static.cninfo.com.cn/finalpage/2026-04-25/1225185746.PDF'
out=pathlib.Path('reports/中国神华/sources/q1_2026_cninfo.pdf')
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'},timeout=60)
print(r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
out.write_bytes(r.content)
print(out.resolve())
