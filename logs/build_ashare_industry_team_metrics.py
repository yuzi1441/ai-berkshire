import json, statistics, csv
from pathlib import Path
# Use latest bottleneck valuation snapshot and manually add broad industry qualitative rows later in report.
base=Path('data/bottleneck-ashare-supertrends')
records=json.loads((base/'ashare_low_valuation_industry_snapshot_20260710.json').read_text(encoding='utf-8'))

groups={
'电网设备/输配电':['002270','600312','002028','600089','000400','600406','601179','688676'],
'民爆/含能材料':['002246','002226','002683','603977','002783','603227'],
'锑钨战略矿物':['002155','601020','600549','000657'],
'AI高速PCB/CCL':['002463','002916','600183','603228'],
'AI光模块/光器件':['300308','300502','300394','002281','000988','688498','688048'],
'半导体设备/材料':['300604','688012','688072','688120','688019','002409','300054','600378','300395'],
'数据中心电源/UPS/温控':['002837','002518','002335','301018'],
'稀土磁材':['600111','000831','300748']
}

def rec(code): return next(x for x in records if x['code']==code)
def med(vals):
    vals=[v for v in vals if v is not None]
    return statistics.median(vals) if vals else None
rows=[]
for g,codes in groups.items():
    rows.append({
        'industry':g,
        'sample_count':len(codes),
        'median_ps':med([rec(c).get('ps_static') for c in codes]),
        'median_pe':med([rec(c).get('pe_ttm_or_dynamic') for c in codes]),
        'median_revenue_growth_pct':med([rec(c).get('revenue_yoy_pct') for c in codes]),
        'low_valuation_count':sum(1 for c in codes if (rec(c).get('pe_ttm_or_dynamic') or 999)<30 and (rec(c).get('ps_static') or 999)<4),
        'representatives':'、'.join(rec(c)['name'] for c in codes[:5])
    })
out=Path('data/industry-team')
out.mkdir(parents=True,exist_ok=True)
(out/'ashare_industry_team_metrics_20260710.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'ashare_industry_team_metrics_20260710.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for row in rows: print(row)
