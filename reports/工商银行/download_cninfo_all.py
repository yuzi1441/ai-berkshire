import requests, json, pathlib, re, time
orgs={'ICBC':('601398','jjxt0000019'),'CCB':('601939','9900003682'),'ABC':('601288','jjxt0000020'),'BOC':('601988','jjxt0000028'),'BOCOM':('601328','9900002841'),'PSBC':('601658','9900005091'),'CMB':('600036','gssh0600036')}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
query_url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
out=pathlib.Path('source_pdfs'); out.mkdir(exist_ok=True)
manifest={}
def query(code,org,category):
    data={'stock':f'{code},{org}','tabName':'fulltext','pageSize':'30','pageNum':'1','column':'sse','plate':'sh','category':category,'seDate':'2026-01-01~2026-07-07','isHLtitle':'true'}
    r=requests.post(query_url,data=data,headers=headers,timeout=20); r.raise_for_status(); return r.json().get('announcements') or []
for name,(code,org) in orgs.items():
    anns=query(code,org,'category_yjdbg_szsh;')+query(code,org,'category_ndbg_szsh;')
    manifest[name]=[]
    print('\n',name)
    for a in anns:
        title=a['announcementTitle']
        if ('2026年第一季度报告' in title and 'H股' not in title) or ('2025年度报告' in title and '摘要' not in title and 'H股' not in title):
            key=('Q1_2026' if '第一季度' in title else 'AR_2025')
            fname=f'{name}_{key}.pdf'
            url='http://static.cninfo.com.cn/'+a['adjunctUrl']
            print(fname,title,url,a.get('announcementTime'))
            rr=requests.get(url,headers=headers,timeout=60)
            print(' ',rr.status_code,len(rr.content),rr.content[:4])
            (out/fname).write_bytes(rr.content)
            manifest[name].append({**a,'download_url':url,'file':str(out/fname)})
pathlib.Path('source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
