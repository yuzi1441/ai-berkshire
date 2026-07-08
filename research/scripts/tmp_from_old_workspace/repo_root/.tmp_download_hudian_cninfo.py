import requests, pathlib, re, json, time
annos={
 '2025_annual': ('1225027832','2026-03-25','沪电股份2025年年度报告.pdf'),
 '2026_q1': ('1225147393','2026-04-23','沪电股份2026年一季度报告.pdf'),
 '2025_h1': ('1224535064','2025-08-22','沪电股份2025年半年度报告.pdf'),
 '2025_q3': ('1224755010','2025-10-29','沪电股份2025年三季度报告.pdf'),
 '2024_annual': ('1222896592','2025-03-26','沪电股份2024年年度报告.pdf'),
}
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','Accept':'application/json,text/plain,*/*'}
out=[]
for key,(aid,tm,name) in annos.items():
    url='http://www.cninfo.com.cn/new/announcement/bulletin_detail'
    params={'announceId':aid,'flag':'true','announceTime':tm}
    r=s.post(url, params=params, headers=headers, timeout=25)
    print(key, r.status_code, r.text[:200])
    data=r.json()
    adj=data['announcement']['adjunctUrl']
    pdfurl='http://static.cninfo.com.cn/'+adj
    pr=s.get(pdfurl, headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}, timeout=60)
    print(' pdf', pr.status_code, pr.headers.get('content-type'), len(pr.content), pdfurl)
    path=pathlib.Path('sources/沪电股份')/name
    path.write_bytes(pr.content)
    out.append({'key':key,'aid':aid,'title':data['announcement'].get('announcementTitle'),'time':data['announcement'].get('announcementTime'),'adjunctUrl':adj,'pdfurl':pdfurl,'file':str(path),'bytes':len(pr.content)})
pathlib.Path('sources/沪电股份/cninfo_manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
