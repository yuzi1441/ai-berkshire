import re, pandas as pd, requests
from pathlib import Path
links=pd.read_csv('data/大型变压器/cninfo_report_links_20260708.csv', dtype=str)
out=Path('research/source_docs/大型变压器')
out.mkdir(parents=True, exist_ok=True)
rows=[]
for _,r in links.iterrows():
    title=str(r['title'])
    if r['keyword']!='2025年年度报告': continue
    if '摘要' in title or 'ERROR' in title: continue
    url=str(r['url'])
    m=re.search(r'announcementId=(\d+).*announcementTime=(\d{4}-\d{2}-\d{2})', url)
    if not m: continue
    aid,date=m.group(1),m.group(2)
    pdf_url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
    code=r['code'].zfill(6)
    fname=f'{code}_{title.replace("/","_")}_{date}.PDF'
    path=out/fname
    try:
        resp=requests.get(pdf_url,timeout=30)
        ok=resp.status_code==200 and resp.content[:4]==b'%PDF'
        if ok and not path.exists(): path.write_bytes(resp.content)
        rows.append({'code':code,'title':title,'date':date,'pdf_url':pdf_url,'path':str(path),'bytes':len(resp.content),'ok':ok})
        print(code, ok, len(resp.content), pdf_url)
    except Exception as e:
        rows.append({'code':code,'title':title,'date':date,'pdf_url':pdf_url,'path':str(path),'bytes':0,'ok':False,'error':repr(e)})
pd.DataFrame(rows).to_csv('data/大型变压器/cninfo_annual_pdf_downloads_20260708.csv',index=False,encoding='utf-8-sig')
