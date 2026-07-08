from urllib.parse import urlencode
from urllib.request import Request, urlopen
import csv, json, time
from pathlib import Path

codes = {
 '600406':('SH','国电南瑞','电网自动化/继保/调度'),
 '002028':('SZ','思源电气','高压开关/GIS/互感器/海外'),
 '688676':('SH','金盘科技','干式变压器/数字化工厂/AIDC'),
 '600089':('SH','特变电工','变压器/特高压/新能源'),
 '601179':('SH','中国西电','一次设备/特高压'),
 '600312':('SH','平高电气','高压开关/GIS'),
 '002837':('SZ','英维克','数据中心温控/液冷'),
 '301018':('SZ','申菱环境','数据中心温控/液冷'),
}

def fetch_fin(code, market):
    params={
        'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL',
        'filter':f'(SECUCODE="{code}.{market}")(REPORT_TYPE="年报")',
        'p':'1','ps':'1','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
    url='https://datacenter.eastmoney.com/securities/api/data/get?'+urlencode(params)
    req=Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urlopen(req, timeout=20) as r:
        data=json.loads(r.read().decode('utf-8'))
    rows=data.get('result',{}).get('data',[])
    return rows[0] if rows else {}

def fetch_quote(codes):
    # use Tencent via PowerShell-created raw? Here use urllib GBK decode.
    q=[]
    for code,(market,_,_) in codes.items():
        prefix='sh' if market=='SH' else 'sz'
        q.append(prefix+code)
    url='https://qt.gtimg.cn/q='+','.join(q)
    req=Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urlopen(req, timeout=20) as r:
        raw=r.read().decode('gbk', errors='replace')
    result={}
    for part in raw.split(';'):
        if '="' not in part: continue
        fields=part.split('"')[1].split('~')
        if len(fields)>46:
            result[fields[2]]={
                'quote_name':fields[1], 'price':fields[3], 'change_pct':fields[32],
                'turnover_amt_wan':fields[37], 'pe':fields[39], 'market_cap_yi':fields[45],
                'pb':fields[46], 'time':fields[30]}
    return result

quotes=fetch_quote(codes)
out=[]
for code,(market,name,subsector) in codes.items():
    fin=fetch_fin(code, market); time.sleep(0.1)
    q=quotes.get(code,{})
    revenue=fin.get('TOTALOPERATEREVE')
    profit=fin.get('PARENTNETPROFIT')
    ocf_per_share=fin.get('MGJYXJJE')
    eps=fin.get('EPSJB')
    shares=fin.get('TOTAL_SHARE')
    ocf = (ocf_per_share or 0) * (shares or 0)
    out.append({
        'code':code+'.'+market, 'name':name, 'subsector':subsector,
        'price':q.get('price'), 'market_cap_yi':q.get('market_cap_yi'), 'pe_ttm':q.get('pe'), 'pb':q.get('pb'), 'change_pct':q.get('change_pct'), 'quote_time':q.get('time'),
        'report':fin.get('REPORT_DATE_NAME'), 'notice_date':fin.get('NOTICE_DATE'),
        'revenue_yi': round(revenue/1e8,2) if revenue is not None else '',
        'net_profit_yi': round(profit/1e8,2) if profit is not None else '',
        'revenue_yoy_pct': fin.get('TOTALOPERATEREVETZ'), 'net_profit_yoy_pct': fin.get('PARENTNETPROFITTZ'),
        'roe_pct':fin.get('ROEJQ'), 'debt_ratio_pct':fin.get('ZCFZL'),
        'ocf_est_yi': round(ocf/1e8,2) if ocf else '',
        'ocf_to_np': round(ocf/profit,2) if ocf and profit else '',
        'source_quote':'Tencent qt.gtimg.cn', 'source_fin':'Eastmoney datacenter RPT_F10_FINANCE_MAINFINADATA'
    })

path=Path('data/dc_electrical_ashare_candidates_20260706.csv')
with path.open('w', newline='', encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)
print(path, len(out))
