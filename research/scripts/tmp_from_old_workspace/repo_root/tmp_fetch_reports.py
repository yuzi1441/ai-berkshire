import requests, re, json, time, pathlib
root=pathlib.Path.cwd()
out=root/'reports'/'四方股份'/'sources'
out.mkdir(parents=True, exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'}
# Query SSE announcements
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={'jsonCallBack':'jsonpCallback123456','isPagination':'true','productId':'601126','keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'DQBG','period':'','beginDate':'2025-01-01','endDate':'2026-07-07','pageHelp.pageSize':'50','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':str(int(time.time()*1000))}
r=requests.get(url,params=params,headers=headers,timeout=30)
r.raise_for_status()
text=r.text
m=re.search(r'^[^(]+\((.*)\)$', text, re.S)
data=json.loads(m.group(1) if m else text)
items=data['pageHelp']['data']
for it in items:
    print(it['SSEDATE'], it['TITLE'], it.get('URL'))
# choose Q1 2026 and 2025 annual
wanted=[]
for it in items:
    title=it['TITLE']
    if '2026年第一季度报告' in title or '2025年年度报告' in title:
        wanted.append(it)
for it in wanted:
    pdf_url='https://www.sse.com.cn'+it['URL']
    fname='601126_'+it['TITLE'].replace('/','_').replace(' ','')+'.pdf'
    path=out/fname
    rr=requests.get(pdf_url,headers=headers,timeout=60)
    print('download', pdf_url, rr.status_code, rr.headers.get('content-type'), len(rr.content))
    path.write_bytes(rr.content)
    print('saved', path, path.stat().st_size)