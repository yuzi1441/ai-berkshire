import requests, re, json, pathlib, akshare as ak, pandas as pd
pd.set_option('display.max_colwidth', 200)
df=ak.stock_zh_a_disclosure_report_cninfo(symbol='600900', market='沪深京', category='', start_date='20260101', end_date='20260707')
keys=['第七届董事会第一次','第七届董事会第二次','第一次临时股东会决议','董事会换届选举','半年度发电量','2026年第一季度报告','2025年年度报告','2025年度利润分配']
sel=[]
for _,r in df.iterrows():
    title=str(r['公告标题'])
    if any(k in title for k in keys):
        sel.append(r.to_dict())
print('selected', len(sel))
for r in sel[:30]: print(r['公告时间'], r['公告标题'], r['公告链接'])
path=pathlib.Path('data/长江电力/cninfo_selected_2026.json')
path.write_text(json.dumps(sel, ensure_ascii=False, indent=2), encoding='utf-8')
# fetch details html and parse pdf URL fragments
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
for r in sel[:15]:
    url=r['公告链接']
    try:
        html=s.get(url, timeout=20).text
        print('\nTITLE', r['公告标题'], 'html', len(html))
        for pat in [r'announcementId=([^&]+)', r'finalpage/[^"\']+?\.PDF', r'adjunctUrl":"([^" ]+)', r'pdfUrl":"([^" ]+)']:
            m=re.findall(pat, html, flags=re.I)
            if m: print('PAT', pat, m[:5])
        pathlib.Path('data/长江电力/cninfo_html_'+str(r['公告链接']).split('announcementId=')[1].split('&')[0]+'.html').write_text(html, encoding='utf-8')
    except Exception as e: print('ERR', e)
