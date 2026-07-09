import yfinance as yf, json, csv
candidates={
'002270.SZ':'华明装备','600312.SS':'平高电气','002028.SZ':'思源电气','601179.SS':'中国西电','600089.SS':'特变电工','000400.SZ':'许继电气','600406.SS':'国电南瑞','688676.SS':'金盘科技','002837.SZ':'英维克','002518.SZ':'科士达','002335.SZ':'科华数据','301018.SZ':'申菱环境','300308.SZ':'中际旭创','300502.SZ':'新易盛','300394.SZ':'天孚通信','002281.SZ':'光迅科技','000988.SZ':'华工科技','688498.SS':'源杰科技','688048.SS':'长光华芯','002463.SZ':'沪电股份','002916.SZ':'深南电路','600183.SS':'生益科技','603228.SS':'景旺电子','688072.SS':'拓荆科技','300604.SZ':'长川科技','688012.SS':'中微公司','002409.SZ':'雅克科技','300054.SZ':'鼎龙股份','002643.SZ':'万润股份','688550.SS':'瑞联新材','300395.SZ':'菲利华','000519.SZ':'中兵红箭','002080.SZ':'中材科技','600378.SS':'昊华科技','002156.SZ':'通富微电','600584.SS':'长电科技','688120.SS':'华海清科','688019.SS':'安集科技'}
out=[]
for s,name in candidates.items():
    try:
        info=yf.Ticker(s).get_info()
        mc=info.get('marketCap'); rev=info.get('totalRevenue')
        ps=info.get('priceToSalesTrailing12Months') or (mc/rev if mc and rev else None)
        out.append({'ticker':s,'cn_name':name,'yf_name':info.get('shortName'),'currency':info.get('currency'),'price':info.get('currentPrice'),'market_cap':mc,'revenue_ttm':rev,'ps_ttm':ps,'pe_ttm':info.get('trailingPE'),'forward_pe':info.get('forwardPE'),'revenue_growth_yoy':info.get('revenueGrowth'),'profit_margin':info.get('profitMargins')})
    except Exception as e:
        out.append({'ticker':s,'cn_name':name,'error':str(e)})
from pathlib import Path
base=Path('data/bottleneck-ashare-supertrends'); base.mkdir(parents=True,exist_ok=True)
(base/'ashare_valuation_snapshot_20260708.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
with (base/'ashare_valuation_snapshot_20260708.csv').open('w',newline='',encoding='utf-8-sig') as f:
    fields=list(out[0].keys()); w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(out)
for d in out:
    if d.get('market_cap'):
        print(d['ticker'],d['cn_name'],round(d['market_cap']/1e8,1),round((d.get('revenue_ttm') or 0)/1e8,1),d.get('ps_ttm'),d.get('pe_ttm'),d.get('revenue_growth_yoy'))
    else: print('MISS',d)
