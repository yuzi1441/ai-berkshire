import requests, pathlib
base='http://static.cninfo.com.cn/'
files={
 '2026_equity_distribution.pdf':'finalpage/2026-07-06/1225410284.PDF',
 '2026_reorg_newshares_apr9.pdf':'finalpage/2026-04-09/1225086585.PDF',
 '2026_finance_company_related_jun26.pdf':'finalpage/2026-06-26/1225387618.PDF',
 '2026_director_pay_jun27.pdf':'finalpage/2026-06-27/1225393355.PDF'
}
out=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\中国神华\sources')
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
 r=requests.get(base+path,headers=headers,timeout=40)
 print(name,r.status_code,r.headers.get('content-type'),len(r.content))
 (out/name).write_bytes(r.content)