import requests, json
from pathlib import Path
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
url='http://static.cninfo.com.cn/finalpage/2026-04-11/1225096189.PDF'
r=requests.get(url,headers=headers,timeout=30)
print(r.status_code,len(r.content),r.content[:4])
Path('1225096189_2026Q1.PDF').write_bytes(r.content)