import json, csv, math, re
from pathlib import Path
from datetime import datetime
import requests
import akshare as ak

codes = [
    ("601179", "sh601179", "中国西电", "核心大型/特高压变压器"),
    ("600089", "sh600089", "特变电工", "大型变压器+线缆+新能源多元化"),
    ("600550", "sh600550", "保变电气", "大型/特高压变压器"),
    ("002028", "sz002028", "思源电气", "输变电一次设备+电力电子"),
    ("688676", "sh688676", "金盘科技", "干式变压器+数据中心/新能源"),
    ("002270", "sz002270", "华明装备", "分接开关/变压器核心部件"),
    ("002922", "sz002922", "伊戈尔", "新能源/工控变压器及电源"),
    ("301012", "sz301012", "扬电科技", "节能电力变压器/配网"),
    ("002112", "sz002112", "三变科技", "油浸式/干式变压器"),
    ("600019", "sh600019", "宝钢股份", "取向硅钢上游"),
    ("000959", "sz000959", "首钢股份", "电工钢上游"),
    ("600362", "sh600362", "江西铜业", "铜材上游"),
]

def fnum(x):
    try:
        if x is None or (isinstance(x,float) and math.isnan(x)): return None
        return float(x)
    except Exception:
        return None

def safe_ak(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return None

def row_metric(df, name, col):
    if df is None: return None
    try:
        s = df[df['指标'].astype(str).str.contains(name, regex=False, na=False)]
        if s.empty or col not in df.columns: return None
        return fnum(s.iloc[0][col])
    except Exception:
        return None

def ind_metric(df, date, name):
    if df is None: return None
    try:
        s = df[df['日期'].astype(str)==date]
        if s.empty or name not in df.columns: return None
        return fnum(s.iloc[0][name])
    except Exception:
        return None

def tencent_quote(tcode):
    txt = requests.get('https://qt.gtimg.cn/q='+tcode, timeout=10).text.strip()
    raw = txt.split('="',1)[1].rstrip('";')
    p = raw.split('~')
    return {
        'raw': raw,
        'name': p[1], 'code': p[2], 'price': fnum(p[3]), 'preclose': fnum(p[4]), 'open': fnum(p[5]),
        'time': p[30] if len(p)>30 else None, 'change': fnum(p[31]) if len(p)>31 else None,
        'pct': fnum(p[32]) if len(p)>32 else None, 'high': fnum(p[33]) if len(p)>33 else None,
        'low': fnum(p[34]) if len(p)>34 else None, 'turnover_pct': fnum(p[38]) if len(p)>38 else None,
        'pe_ttm': fnum(p[39]) if len(p)>39 else None,
        'amplitude_pct': fnum(p[43]) if len(p)>43 else None,
        'float_mkt_cap_yi': fnum(p[44]) if len(p)>44 else None,
        'total_mkt_cap_yi': fnum(p[45]) if len(p)>45 else None,
        'pb': fnum(p[46]) if len(p)>46 else None,
    }

records=[]
for code,tcode,name,role in codes:
    q=tencent_quote(tcode)
    fin=safe_ak(ak.stock_financial_abstract, code)
    ind=safe_ak(ak.stock_financial_analysis_indicator, code, '2024')
    rec={
        'code': code, 'tencent_code': tcode, 'name': name, 'role': role,
        'quote_time': q.get('time'), 'price_yuan': q.get('price'), 'pct_change': q.get('pct'),
        'market_cap_yi': q.get('total_mkt_cap_yi'), 'float_market_cap_yi': q.get('float_mkt_cap_yi'),
        'pe_ttm_tencent': q.get('pe_ttm'), 'pb_tencent': q.get('pb'),
        'implied_total_shares_yi': (q.get('total_mkt_cap_yi')/q.get('price') if q.get('price') else None),
    }
    for date,label in [('20251231','2025'),('20260331','2026Q1'),('20241231','2024')]:
        rev=row_metric(fin,'营业总收入',date)
        np=row_metric(fin,'归母净利润',date)
        cf=row_metric(fin,'经营活动产生的现金流量净额',date)
        rec[f'revenue_{label}_yi']= rev/1e8 if rev is not None else None
        rec[f'net_profit_{label}_yi']= np/1e8 if np is not None else None
        rec[f'op_cf_{label}_yi']= cf/1e8 if cf is not None else None
    for date,label in [('2025-12-31','2025'),('2026-03-31','2026Q1')]:
        rec[f'gross_margin_{label}_pct']=ind_metric(ind,date,'销售毛利率(%)')
        rec[f'net_margin_{label}_pct']=ind_metric(ind,date,'销售净利率(%)')
        rec[f'roe_weighted_{label}_pct']=ind_metric(ind,date,'加权净资产收益率(%)')
        rec[f'asset_liability_{label}_pct']=ind_metric(ind,date,'资产负债率(%)')
    records.append(rec)

outdir=Path('data/大型变压器')
outdir.mkdir(parents=True, exist_ok=True)
json_path=outdir/'ashare_transformer_snapshot_20260708.json'
csv_path=outdir/'ashare_transformer_snapshot_20260708.csv'
json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=list(records[0].keys()))
    w.writeheader(); w.writerows(records)
print(json_path.resolve())
print(csv_path.resolve())
print(json.dumps(records[:3], ensure_ascii=False, indent=2)[:2000])
