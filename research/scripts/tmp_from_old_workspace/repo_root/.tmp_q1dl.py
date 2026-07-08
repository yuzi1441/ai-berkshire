import requests, pathlib, json, time
out=pathlib.Path('sources/huaming'); out.mkdir(exist_ok=True,parents=True)
url='https://static.cninfo.com.cn/finalpage/2026-04-27/1225181771.PDF'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'},timeout=60)
print(r.status_code,len(r.content),r.content[:4])
if r.status_code==200: (out/'1225181771_2026年一季度报告.PDF').write_bytes(r.content)
