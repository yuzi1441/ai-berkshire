from pathlib import Path
from urllib.request import build_opener, ProxyHandler, Request
import json, csv, time, math
from datetime import datetime

import akshare as ak

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
STAMP=datetime.now().strftime('%Y%m%d')
OUT_CSV=DATA/f'power_resource_funnel_candidates_{STAMP}.csv'
SUMMARY=DATA/f'power_resource_funnel_summary_{STAMP}.json'

A_CANDIDATES=[
    # pure quality pool + major power/resource names
    ('长江电力','600900','SH','水电','A/B/C','质量池；全球级长江干流水电资产'),
    ('中国神华','601088','SH','煤炭一体化/煤电','A/B/C','质量池；煤炭、电力、铁路港口一体化现金牛'),
    ('紫金矿业','601899','SH','铜金矿业','A/B/C','质量池；全球化铜金资源龙头'),
    ('陕西煤业','601225','SH','煤炭','A/B/C','质量池；高股息煤炭龙头'),
    ('华能水电','600025','SH','水电','A/C','质量池；澜沧江水电平台'),
    ('兖矿能源','600188','SH','煤炭','A/B/C','质量池；煤炭弹性更高但周期更强'),
    ('国投电力','600886','SH','水火风光综合电力','A/B/C','质量池；雅砻江水电核心权益'),
    ('川投能源','600674','SH','水电投资','A/C','雅砻江水电权益平台'),
    ('桂冠电力','600236','SH','水电/火电','A/B','广西水电为主，来水波动大'),
    ('中国广核','003816','SZ','核电','A/C','核电运营龙头之一'),
    ('中国核电','601985','SH','核电/新能源','A/C','核电运营龙头之一'),
    ('华电国际','600027','SH','火电','A/B','火电低PE，煤价与电价敏感'),
    ('华能国际','600011','SH','火电','A/B','火电龙头，负债与燃料成本压力'),
    ('国电电力','600795','SH','综合电力','A/B','大型电力平台'),
    ('浙能电力','600023','SH','火电','A/B','地方火电平台'),
    ('三峡能源','600905','SH','新能源发电','A/C','风光运营，估值较高'),
    ('申能股份','600642','SH','综合电力/燃气','A/B','上海公用事业平台'),
    ('深圳能源','000027','SZ','综合电力/环保','A/B','区域电力环保平台'),
    ('皖能电力','000543','SZ','火电','A/B','区域火电平台'),
    ('中国石油','601857','SH','油气','A/C','央企油气上游与炼化'),
    ('中国石化','600028','SH','炼化/油气','A/C','炼化营销龙头，上游弹性较弱'),
    ('中国海油','600938','SH','海上油气','A/C','海上油气上游龙头'),
    ('宝丰能源','600989','SH','煤化工','A/C','煤化工龙头，非纯资源股'),
    ('中国铝业','601600','SH','铝','A/C','铝央企龙头'),
    ('山东黄金','600547','SH','黄金','A/B','黄金资源，成本与金价敏感'),
    ('中金黄金','600489','SH','黄金','A/B','央企黄金资源'),
    ('江西铜业','600362','SH','铜','A/C','铜冶炼+资源，冶炼属性稀释'),
    ('云铝股份','000807','SZ','铝','A/B','水电铝，周期强'),
    ('神火股份','000933','SZ','煤铝','A/B','煤铝双主业'),
    ('西部矿业','601168','SH','铜铅锌','A/B','有色资源弹性'),
    ('洛阳钼业','603993','SH','铜钴钼','A/C','全球化矿业，周期与地缘风险'),
    ('铜陵有色','000630','SZ','铜','A/B','铜冶炼属性重'),
    ('淮北矿业','600985','SH','煤炭/焦煤','A/B','焦煤煤化工'),
    ('山金国际','000975','SZ','黄金/有色','A/B','黄金弹性'),
    ('郑煤机','601717','SH','煤机设备','A/B','设备而非资源，列观察'),
    ('中国稀土','000831','SZ','稀土','B/C','资源主题强，估值和盈利波动大'),
    ('北方稀土','600111','SH','稀土','A/C','稀土龙头但估值与政策强相关'),
    ('驰宏锌锗','600497','SH','铅锌锗','A/B','有色资源中盘股'),
    ('厦门钨业','600549','SH','钨钼稀土材料','A/B','材料属性较重'),
    ('赤峰黄金','600988','SH','黄金','A/B','民营黄金弹性'),
]

GLOBAL=[
    ('中国海洋石油','00883','HK','油气','C','港股油气上游高股息参考'),
    ('中国神华H','01088','HK','煤炭一体化','C','A/H折价与股息税比较'),
    ('紫金矿业H','02899','HK','铜金矿业','C','A/H估值比较'),
    ('Exxon Mobil','XOM','US','油气','C','全球油气巨头参考'),
    ('Chevron','CVX','US','油气','C','全球油气巨头参考'),
    ('NextEra Energy','NEE','US','公用事业/新能源','C','美股电力公用事业估值参考'),
    ('Southern Company','SO','US','公用事业','C','美股电力公用事业估值参考'),
    ('Freeport-McMoRan','FCX','US','铜金','C','全球铜矿参考'),
    ('Southern Copper','SCCO','US','铜','C','全球铜矿参考'),
]

def sym(code, market):
    if market=='SH': return 'sh'+code
    if market=='SZ': return 'sz'+code
    if market=='HK': return 'hk'+code
    if market=='US': return 'us'+code
    return code

def qq_quotes(items):
    opener=build_opener(ProxyHandler({}))
    res={}
    syms=[sym(c,m) for _,c,m,_,_,_ in items]
    for i in range(0,len(syms),50):
        url='https://qt.gtimg.cn/q='+','.join(syms[i:i+50])
        txt=opener.open(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=20).read().decode('gbk','replace')
        for part in txt.split(';'):
            if '=' not in part or '"' not in part: continue
            payload=part.split('"',1)[1].rsplit('"',1)[0]
            f=payload.split('~')
            if len(f)<47: continue
            code=f[2]
            res[code]={
                'quote_name': f[1], 'code': code, 'price': f[3], 'prev_close': f[4], 'open': f[5],
                'volume_lot': f[6], 'quote_time': f[30], 'change': f[31], 'change_pct': f[32],
                'high': f[33], 'low': f[34], 'turnover_amt_wan': f[37] if len(f)>37 else '',
                'turnover_rate': f[38] if len(f)>38 else '', 'pe': f[39] if len(f)>39 else '',
                'float_market_cap_yi': f[44] if len(f)>44 else '', 'market_cap_yi': f[45] if len(f)>45 else '',
                'pb': f[46] if len(f)>46 else '', 'high_52w': f[47] if len(f)>47 else '', 'low_52w': f[48] if len(f)>48 else '',
                'dividend_yield': f[65] if len(f)>65 else '', 'ttm_pe2': f[52] if len(f)>52 else '',
            }
    return res

def fnum(x):
    try:
        if x is None or x=='': return None
        if isinstance(x,float) and math.isnan(x): return None
        return float(x)
    except Exception: return None

def get_metric(code):
    out={}
    try:
        df=ak.stock_financial_abstract(symbol=code)
        for metric,key in [('归母净利润','np_2025'),('营业总收入','rev_2025'),('经营现金流量净额','ocf_2025'),('净资产收益率(ROE)','roe_2025'),('资产负债率','debt_asset_2025'),('经营活动净现金/归属母公司的净利润','ocf_np_2025')]:
            rows=df[df['指标'].eq(metric)]
            if not rows.empty:
                out[key]=fnum(rows.iloc[0].get('20251231'))
                out[key.replace('2025','2026q1')]=fnum(rows.iloc[0].get('20260331'))
                out[key.replace('2025','2024')]=fnum(rows.iloc[0].get('20241231'))
    except Exception as e:
        out['financial_error']=repr(e)[:200]
    return out

def hist_stats(code, market):
    out={}
    try:
        s=sym(code,market)
        df=ak.stock_zh_a_hist_tx(symbol=s, start_date='20260401', end_date='20260706')
        if len(df)>0:
            first=float(df.iloc[0]['close']); last=float(df.iloc[-1]['close'])
            out['chg_90d_pct']=round((last/first-1)*100,2) if first else None
            out['avg_amount_90d_lot']=round(float(df['amount'].tail(60).mean()),0)
            out['last_hist_close']=last
    except Exception as e:
        out['hist_error']=repr(e)[:120]
    return out

rows=[]
quotes=qq_quotes(A_CANDIDATES+GLOBAL)
for name,code,market,sector,cat,note in A_CANDIDATES:
    row={'name':name,'code':code,'market':'A股-'+market,'subsector':sector,'entry_category':cat,'note':note}
    row.update(quotes.get(code,{}))
    row.update(get_metric(code))
    row.update(hist_stats(code,market))
    # convert financial values to 亿
    for k in list(row.keys()):
        if k.startswith(('np_','rev_','ocf_')) and isinstance(row[k],(int,float)):
            row[k+'_yi']=round(row[k]/1e8,2)
    rows.append(row)
    time.sleep(0.1)

for name,code,market,sector,cat,note in GLOBAL:
    row={'name':name,'code':code,'market':market,'subsector':sector,'entry_category':cat,'note':note}
    row.update(quotes.get(code,{}))
    rows.append(row)

DATA.mkdir(exist_ok=True)
fields=[]
for r in rows:
    for k in r.keys():
        if k not in fields: fields.append(k)
with OUT_CSV.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
summary={
    'generated_at':datetime.now().isoformat(timespec='seconds'),
    'data_cutoff':'2026-07-06 Tencent quote time per row; AkShare financial abstract latest 2025A/2026Q1 where available',
    'count_a':len(A_CANDIDATES),'count_global':len(GLOBAL),'output':str(OUT_CSV.relative_to(ROOT)),
    'sources':{
        'tencent_quote':'https://qt.gtimg.cn/q={symbols}',
        'akshare_financial_abstract':'akshare.stock_financial_abstract (Sina/EM financial abstract wrapper)',
        'akshare_hist_tx':'akshare.stock_zh_a_hist_tx (Tencent historical quotes)',
        'local_prior_report':'reports/A股低估行业漏斗-funnel-20260706.md'
    }
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
