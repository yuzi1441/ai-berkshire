import requests, json, pathlib, time
stocks={
'ICBC':'601398,jjxt0000019','CCB':'601939,jjxt0000024','ABC':'601288,jjxt0000023','BOC':'601988,jjxt0000026','BOCOM':'601328,jjxt0000025','PSBC':'601658,gfbj0833018','CMB':'600036,gssh0600036'}
# need verify org ids via topSearch if unknown
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
# first lookup exact orgs
for name, st in list(stocks.items()):
    code=st.split(',')[0]
    r=requests.post('http://www.cninfo.com.cn/new/information/topSearch/query',data={'keyWord':code,'maxNum':'10'},headers=headers,timeout=20)
    arr=r.json(); print(name, code, arr[:1])
