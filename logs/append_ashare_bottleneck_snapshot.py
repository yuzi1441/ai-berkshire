import json,csv,time,urllib.request,re
from pathlib import Path
extra=[('002246','SZ','北化股份','硝化棉/含能材料'),('002226','SZ','江南化工','民爆/工业炸药'),('002683','SZ','广东宏大','矿服民爆/防务装备'),('603977','SH','国泰集团','民爆/电子雷管'),('002783','SZ','凯龙股份','民爆/硝酸铵'),('002827','SZ','高争民爆','民爆'),('603227','SH','雪峰科技','民爆/硝酸铵'),('600549','SH','厦门钨业','钨/稀土/材料'),('000657','SZ','中钨高新','钨硬质合金'),('002155','SZ','湖南黄金','锑/黄金'),('601020','SH','华钰矿业','锑/有色'),('600111','SH','北方稀土','稀土'),('000831','SZ','中国稀土','稀土'),('300748','SZ','金力永磁','稀土永磁')]
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}
def fetch(url,encoding='utf-8'):
    return urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20).read().decode(encoding,'ignore')
def quote(code,market):
    txt=fetch(f"https://qt.gtimg.cn/q={'sz' if market=='SZ' else 'sh'}{code}",'gbk')
    m=re.search(r'="(.*)"',txt); f=m.group(1).split('~') if m else []
    def num(i):
        try:return float(f[i]) if f[i] else None
        except:return None
    return {'price':num(3),'pct_chg':num(32),'pe_ttm_or_dynamic':num(39),'total_mcap_yi':num(45),'pb':num(46),'timestamp':f[30] if len(f)>30 else None}
def fin(code,market):
    data=json.loads(fetch(f'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=1&code={market}{code}'))
    rows=data.get('data') or []; row=next((r for r in rows if '年报' in str(r.get('REPORT_TYPE',''))),rows[0] if rows else {})
    return {'report_date':row.get('REPORT_DATE_NAME') or row.get('REPORT_DATE'),'revenue':row.get('TOTALOPERATEREVE'),'revenue_yoy_pct':row.get('TOTALOPERATEREVETZ'),'parent_np':row.get('PARENTNETPROFIT'),'np_yoy_pct':row.get('PARENTNETPROFITTZ')}
base=Path('data/bottleneck-ashare-supertrends')
out=json.loads((base/'ashare_bottleneck_snapshot_20260708.json').read_text(encoding='utf-8'))
for code,market,name,theme in extra:
    rec={'code':code,'market':market,'ticker':f'{code}.{market}','name':name,'bottleneck_theme':theme}
    try:rec.update(quote(code,market))
    except Exception as e:rec['quote_error']=repr(e)
    try:rec.update(fin(code,market))
    except Exception as e:rec['fin_error']=repr(e)
    rec['revenue_yi']=rec['revenue']/1e8 if isinstance(rec.get('revenue'),(int,float)) else None
    rec['parent_np_yi']=rec['parent_np']/1e8 if isinstance(rec.get('parent_np'),(int,float)) else None
    rec['ps_static']=rec['total_mcap_yi']/rec['revenue_yi'] if rec.get('total_mcap_yi') and rec.get('revenue_yi') else None
    out.append(rec)
(base/'ashare_bottleneck_snapshot_20260708.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
fields=list(out[0].keys())
with (base/'ashare_bottleneck_snapshot_20260708.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(out)
for r in out[-len(extra):]: print(r['ticker'],r['name'],r.get('total_mcap_yi'),r.get('revenue_yi'),r.get('ps_static'),r.get('pe_ttm_or_dynamic'),r.get('revenue_yoy_pct'))
