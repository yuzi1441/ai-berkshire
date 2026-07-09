import json, csv, math, requests, re
from pathlib import Path
from datetime import datetime
import akshare as ak

companies = [
    ("002270", "sz002270", "华明装备", "分接开关/变压器核心部件"),
    ("688676", "sh688676", "金盘科技", "干式变压器+数据中心/新能源"),
    ("601179", "sh601179", "中国西电", "UHV/大型输变电装备国家队"),
    ("002028", "sz002028", "思源电气", "输变电一次设备平台"),
    ("600089", "sh600089", "特变电工", "输变电+线缆+新能源/能源多元化"),
]

def fnum(x):
    try:
        if x is None or (isinstance(x,float) and math.isnan(x)): return None
        return float(x)
    except Exception:
        return None

def get_metric(df, label, date='20251231'):
    s=df[df['指标'].astype(str).eq(label)]
    if s.empty:
        s=df[df['指标'].astype(str).str.contains(label, regex=False, na=False)]
    if s.empty or date not in df.columns: return None
    return fnum(s.iloc[0][date])

def quote(tcode):
    txt=requests.get('https://qt.gtimg.cn/q='+tcode,timeout=10).text.strip()
    raw=txt.split('="',1)[1].rstrip('";')
    p=raw.split('~')
    return {
        'quote_time': p[30] if len(p)>30 else None,
        'price': fnum(p[3]), 'pct_change': fnum(p[32]) if len(p)>32 else None,
        'turnover_pct': fnum(p[38]) if len(p)>38 else None,
        'pe_ttm': fnum(p[39]) if len(p)>39 else None,
        'market_cap_yi': fnum(p[45]) if len(p)>45 else None,
        'pb': fnum(p[46]) if len(p)>46 else None,
    }

rows=[]
for code,tcode,name,role in companies:
    q=quote(tcode)
    fin=ak.stock_financial_abstract(code)
    rec={'code':code,'tencent_code':tcode,'name':name,'role':role,**q}
    for date,label in [('20251231','2025'),('20241231','2024'),('20231231','2023'),('20260331','2026Q1')]:
        revenue=get_metric(fin,'营业总收入',date)
        profit=get_metric(fin,'归母净利润',date)
        ocf=get_metric(fin,'经营现金流量净额',date)
        roe=get_metric(fin,'净资产收益率(ROE)',date)
        gross=get_metric(fin,'毛利率',date)
        net_margin=get_metric(fin,'销售净利率',date)
        debt=get_metric(fin,'资产负债率',date)
        ocf_profit=get_metric(fin,'经营活动净现金/归属母公司的净利润',date)
        rec[f'revenue_{label}_yi']= revenue/1e8 if revenue is not None else None
        rec[f'profit_{label}_yi']= profit/1e8 if profit is not None else None
        rec[f'ocf_{label}_yi']= ocf/1e8 if ocf is not None else None
        rec[f'roe_{label}_pct']= roe
        rec[f'gross_margin_{label}_pct']= gross
        rec[f'net_margin_{label}_pct']= net_margin
        rec[f'debt_asset_{label}_pct']= debt
        rec[f'ocf_profit_{label}_pct']= ocf_profit*100 if ocf_profit is not None and abs(ocf_profit) < 10 else ocf_profit
    # growth
    if rec.get('revenue_2025_yi') and rec.get('revenue_2024_yi'):
        rec['revenue_growth_2025_pct']=(rec['revenue_2025_yi']/rec['revenue_2024_yi']-1)*100
    if rec.get('profit_2025_yi') and rec.get('profit_2024_yi'):
        rec['profit_growth_2025_pct']=(rec['profit_2025_yi']/rec['profit_2024_yi']-1)*100
    if q['price'] and q['pe_ttm']:
        rec['eps_ttm_implied']=q['price']/q['pe_ttm']
        rec['shares_yi_implied']=q['market_cap_yi']/q['price'] if q.get('market_cap_yi') else None
    rows.append(rec)

outdir=Path('data/大型变压器')
outdir.mkdir(parents=True, exist_ok=True)
json_path=outdir/'five_stock_funnel_snapshot_20260708.json'
csv_path=outdir/'five_stock_funnel_snapshot_20260708.csv'
json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
with csv_path.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print(json_path.resolve())
print(csv_path.resolve())
for r in rows:
    print(r['name'], r['price'], r['market_cap_yi'], r['pe_ttm'], r['pb'], 'ROE', r['roe_2025_pct'], 'OCF/NP', r['ocf_profit_2025_pct'], 'debt', r['debt_asset_2025_pct'])
