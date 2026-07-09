import requests, re, json, pathlib, csv
codes=['sz300476','sz002463','sz002916','sh600183','sz002384','sh603936','sz301308','sh688183','sz002579']
url='https://qt.gtimg.cn/q='+','.join(codes)
txt=requests.get(url,timeout=15).text
data_dir=pathlib.Path('data/ai-pcb-materials')
log_dir=pathlib.Path('logs')
data_dir.mkdir(parents=True,exist_ok=True)
log_dir.mkdir(exist_ok=True)
(data_dir/'tencent_quote_raw_20260710.txt').write_text(txt,encoding='utf-8')
rows=[]
for line in txt.strip().split('\n'):
    m=re.match(r'v_(\w+)="(.*)";',line)
    if not m:
        continue
    code=m.group(1); f=m.group(2).split('~')
    def get(i):
        return f[i] if i < len(f) else ''
    rows.append({
        'code': code,
        'name': get(1),
        'ticker': get(2),
        'price_cny': get(3),
        'prev_close': get(4),
        'change_pct': get(32),
        'turnover_pct': get(38),
        'pe_dynamic_or_static_field39': get(39),
        'pb_field46': get(46),
        'float_mcap_100m_cny_field44': get(44),
        'total_mcap_100m_cny_field45': get(45),
        'pe_ttm_field52': get(52),
        'eps_ttm_field53': get(53),
        'high_52w_field74': get(74),
        'low_52w_field75': get(75),
        'shares_field84': get(84),
        'raw_field_count': len(f),
    })
for r in rows:
    print(json.dumps(r,ensure_ascii=False))
with (data_dir/'ashare_quote_snapshot_20260710.csv').open('w',newline='',encoding='utf-8-sig') as fp:
    w=csv.DictWriter(fp,fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
