import requests, re, json, pathlib, sys, subprocess, os
from urllib.parse import urljoin
root=pathlib.Path.cwd()
out=root/'reports'/'中国神华'/'sources'
out.mkdir(parents=True, exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
# SSE query for latest periodic reports
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?jsonCallBack=jsonpCallback&isPagination=true&productId=601088&keyWord=&securityType=0101,120100,020100,020200,120200&reportType2=DQBG&reportType=ALL&beginDate=2025-01-01&endDate=2026-07-07&pageHelp.pageSize=30&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1'
r=requests.get(url,headers=headers,timeout=30)
text=r.text
m=re.search(r'jsonpCallback\((.*)\)$', text, re.S)
data=json.loads(m.group(1) if m else text)
items=data['pageHelp']['data']
sel=[]
for it in items:
    if it.get('TITLE') in ['中国神华2026年第一季度报告','中国神华2025年度报告','中国神华2025年年度报告摘要','中国神华2025年第三季度报告','中国神华2025年半年度报告']:
        sel.append(it)
print('selected', [(x['TITLE'],x['SSEDATE'],x['URL']) for x in sel])
for it in sel:
    pdf_url=urljoin('https://www.sse.com.cn', it['URL'])
    fn=it['TITLE'].replace('/','_')+'_'+it['SSEDATE']+'.pdf'
    path=out/fn
    if not path.exists() or path.stat().st_size<1000:
        rr=requests.get(pdf_url,headers=headers,timeout=60)
        print('download', pdf_url, rr.status_code, rr.headers.get('content-type'), len(rr.content))
        path.write_bytes(rr.content)
    it['local_file']=str(path)
(out/'sse_periodic_reports.json').write_text(json.dumps(sel,ensure_ascii=False,indent=2),encoding='utf-8')
# quote from Sina
q=requests.get('https://hq.sinajs.cn/list=sh601088,hk01088',headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
(out/'sina_quote_20260707.txt').write_text(q.text,encoding='gbk',errors='replace')
print(q.text[:1000])
