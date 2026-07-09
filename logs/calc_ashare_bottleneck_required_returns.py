import json
from pathlib import Path
base=Path('data/bottleneck-ashare-supertrends')
out=json.loads((base/'ashare_bottleneck_snapshot_20260708.json').read_text(encoding='utf-8'))
for r in out:
    mc_yi=r.get('total_mcap_yi'); rev_yi=r.get('revenue_yi'); np_yi=r.get('parent_np_yi')
    margin=(np_yi/rev_yi) if rev_yi and np_yi and np_yi>0 else 0.10
    req_np_yi=mc_yi*(1.10**10)/25 if mc_yi else None
    req_rev_yi=req_np_yi/margin if req_np_yi and margin else None
    r['np_margin_static']=margin
    r['required_10y_np_yi_for_10pct_cagr']=req_np_yi
    r['required_10y_rev_yi_for_10pct_cagr']=req_rev_yi
    r['required_rev_multiple_vs_2025']=req_rev_yi/rev_yi if req_rev_yi and rev_yi else None
(base/'ashare_bottleneck_snapshot_20260708.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
for code in ['002270','600312','002028','002463','300308','002246','002683','600549','002155','688676','002837']:
    r=next(x for x in out if x['code']==code)
    print(r['ticker'],r['name'],'req_rev_mult',round(r['required_rev_multiple_vs_2025'],2),'margin',round(r['np_margin_static'],3))
