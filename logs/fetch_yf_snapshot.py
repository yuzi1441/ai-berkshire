import json, csv, math
from pathlib import Path
import yfinance as yf
syms=['GEV','ETN','POWL','LEU','UAMY','MP','FORM','AXTI','VRT','BWXT','LHX','RKLB','LITE','COHR','CIEN','PRY.MI','NEX.PA','NKT.CO','CHG.L','3110.T','4047.T','2802.T','RHM.DE','AII.TO','LYC.AX']
out=[]
for s in syms:
    try:
        info=yf.Ticker(s).get_info()
        mc=info.get('marketCap')
        rev=info.get('totalRevenue')
        ps=info.get('priceToSalesTrailing12Months') or (mc/rev if mc and rev else None)
        pe=info.get('trailingPE')
        margin=info.get('profitMargins')
        assumed_margin = margin if margin and margin>0.05 and margin<0.5 else 0.15
        req_ni_10pct = (mc*(1.10**10)/25) if mc else None
        req_rev_10pct = (req_ni_10pct/assumed_margin) if req_ni_10pct and assumed_margin else None
        out.append({
            'ticker':s,
            'name':info.get('shortName'),
            'currency':info.get('currency'),
            'price':info.get('currentPrice'),
            'market_cap':mc,
            'revenue_ttm':rev,
            'ps_ttm':ps,
            'pe_ttm':pe,
            'forward_pe':info.get('forwardPE'),
            'revenue_growth_yoy':info.get('revenueGrowth'),
            'profit_margin':margin,
            'assumed_margin_for_10y_test':assumed_margin,
            'required_10y_net_income_for_10pct_cagr':req_ni_10pct,
            'required_10y_revenue_for_10pct_cagr':req_rev_10pct,
            'required_revenue_multiple_vs_ttm':(req_rev_10pct/rev if req_rev_10pct and rev else None),
        })
    except Exception as e:
        out.append({'ticker':s,'error':str(e)})
base=Path('data/bottleneck-global-supertrends')
(base/'valuation_snapshot_20260708.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
with (base/'valuation_snapshot_20260708.csv').open('w',newline='',encoding='utf-8') as f:
    fields=list(out[0].keys())
    w=csv.DictWriter(f,fieldnames=fields)
    w.writeheader(); w.writerows(out)
print(base/'valuation_snapshot_20260708.json')
print(base/'valuation_snapshot_20260708.csv')
