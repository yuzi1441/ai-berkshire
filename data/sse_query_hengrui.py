import json, subprocess, urllib.parse
from pathlib import Path

def fetch(begin,end,keyword='',page=1,ps=100):
    base='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
    params={
      'jsonCallBack':'','isPagination':'true','productId':'600276','keyWord':keyword,
      'securityType':'0101,120100,020100,020200,120200','reportType2':'','reportType':'ALL',
      'beginDate':begin,'endDate':end,'pageHelp.pageSize':str(ps),'pageHelp.pageNo':str(page),
      'pageHelp.beginPage':str(page),'pageHelp.cacheSize':'1','pageHelp.endPage':str(page),'_':'1783350000000'}
    url=base+'?'+urllib.parse.urlencode(params)
    txt=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','Referer: https://www.sse.com.cn/','-H','User-Agent: Mozilla/5.0',url],timeout=60).decode('utf-8')
    return json.loads(txt)

for kw in ['年度报告','第一季度报告','2025年年度报告','2026年第一季度报告']:
    d=fetch('2026-01-01','2026-07-06',kw,1,50)
    rows=d.get('pageHelp',{}).get('data',[])
    print('\nKW',kw,'rows',len(rows))
    for r in rows[:10]: print(r.get('SSEDATE'), r.get('TITLE'), 'https://www.sse.com.cn'+r.get('URL',''))
    Path(f'data/sse_{kw}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
