import json, csv, time, urllib.request, re
from pathlib import Path

candidates=[
('002270','SZ','华明装备','电力接入/变压器分接开关'),('600312','SH','平高电气','UHV/GIS/高压开关'),('002028','SZ','思源电气','高压开关/无功补偿/电网设备'),('601179','SH','中国西电','输变电一次设备'),('600089','SH','特变电工','变压器/电缆/新能源电力'),('000400','SZ','许继电气','换流阀/保护自动化'),('600406','SH','国电南瑞','电网自动化/柔直'),('688676','SH','金盘科技','干式变压器/数据中心电力'),
('002837','SZ','英维克','数据中心液冷/温控'),('002518','SZ','科士达','UPS/数据中心电源'),('002335','SZ','科华数据','UPS/数据中心电源'),('301018','SZ','申菱环境','数据中心温控'),
('300308','SZ','中际旭创','800G/1.6T光模块'),('300502','SZ','新易盛','高速光模块'),('300394','SZ','天孚通信','光器件/无源器件'),('002281','SZ','光迅科技','光芯片/光模块'),('000988','SZ','华工科技','激光/光模块'),('688498','SH','源杰科技','激光芯片'),('688048','SH','长光华芯','半导体激光芯片'),
('002463','SZ','沪电股份','AI服务器/交换机PCB'),('002916','SZ','深南电路','PCB/封装基板'),('600183','SH','生益科技','覆铜板/高速材料'),('603228','SH','景旺电子','PCB'),
('300604','SZ','长川科技','半导体测试设备'),('688012','SH','中微公司','刻蚀/MOCVD'),('688072','SH','拓荆科技','薄膜沉积设备'),('688120','SH','华海清科','CMP设备'),('688019','SH','安集科技','CMP抛光液/材料'),('002409','SZ','雅克科技','电子材料/前驱体'),('300054','SZ','鼎龙股份','CMP垫/半导体材料'),
('000519','SZ','中兵红箭','超硬材料/军品'),('600378','SH','昊华科技','含氟材料/特气'),('300395','SZ','菲利华','石英材料/半导体'),('002080','SZ','中材科技','复材/高压气瓶/叶片')]

headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}

def fetch(url, encoding='utf-8'):
    req=urllib.request.Request(url,headers=headers)
    return urllib.request.urlopen(req,timeout=20).read().decode(encoding,'ignore')

def tencent_quote(code, market):
    prefix='sz' if market=='SZ' else 'sh'
    txt=fetch(f'https://qt.gtimg.cn/q={prefix}{code}', 'gbk')
    m=re.search(r'="(.*)"',txt)
    if not m: return {}
    f=m.group(1).split('~')
    def num(i):
        try: return float(f[i]) if f[i] not in ('','--') else None
        except Exception: return None
    return {'price':num(3),'pct_chg':num(32),'pe_ttm_or_dynamic':num(39),'turnover_rate':num(38),'high':num(33),'low':num(34),'circulating_mcap_yi':num(44),'total_mcap_yi':num(45),'pb':num(46),'timestamp':f[30] if len(f)>30 else None}

def eastmoney_fin(code, market):
    sec=f'{market}{code}'
    url=f'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=1&code={sec}'
    data=json.loads(fetch(url))
    rows=data.get('data') or []
    # prefer latest annual report, fallback first row
    row=next((r for r in rows if '年报' in str(r.get('REPORT_TYPE',''))), rows[0] if rows else {})
    return {'report_date':row.get('REPORT_DATE_NAME') or row.get('REPORT_DATE'),'notice_date':row.get('NOTICE_DATE'),'revenue':row.get('TOTALOPERATEREVE'),'revenue_yoy_pct':row.get('TOTALOPERATEREVETZ'),'parent_np':row.get('PARENTNETPROFIT'),'np_yoy_pct':row.get('PARENTNETPROFITTZ'),'gross_profit':row.get('MLR'),'eps':row.get('EPSJB'),'roe_pct':row.get('ROEJQ') or row.get('JQJZCSYL')}

out=[]
for code,market,name,theme in candidates:
    rec={'code':code,'market':market,'ticker':f'{code}.{market}','name':name,'bottleneck_theme':theme}
    try: rec.update(tencent_quote(code, market))
    except Exception as e: rec['quote_error']=repr(e)
    time.sleep(0.05)
    try: rec.update(eastmoney_fin(code, market))
    except Exception as e: rec['fin_error']=repr(e)
    mc=rec.get('total_mcap_yi'); rev=rec.get('revenue')
    rec['revenue_yi']=rev/1e8 if isinstance(rev,(int,float)) else None
    rec['parent_np_yi']=rec.get('parent_np')/1e8 if isinstance(rec.get('parent_np'),(int,float)) else None
    rec['ps_static']=mc/rec['revenue_yi'] if mc and rec.get('revenue_yi') else None
    out.append(rec)

base=Path('data/bottleneck-ashare-supertrends'); base.mkdir(parents=True,exist_ok=True)
(base/'ashare_bottleneck_snapshot_20260708.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
fields=list(out[0].keys())
with (base/'ashare_bottleneck_snapshot_20260708.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(out)
print(base/'ashare_bottleneck_snapshot_20260708.json')
for r in out:
    print(r['ticker'],r['name'],r.get('total_mcap_yi'),r.get('revenue_yi'),r.get('ps_static'),r.get('pe_ttm_or_dynamic'),r.get('revenue_yoy_pct'))
