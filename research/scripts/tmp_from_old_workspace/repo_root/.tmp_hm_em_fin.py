import akshare as ak, pandas as pd, pathlib, json, math
symbol='002270'
out=pathlib.Path('reports/华明装备/sources/eastmoney'); out.mkdir(parents=True,exist_ok=True)
# save main financial tables
abstract=ak.stock_financial_abstract(symbol=symbol)
abstract.to_csv(out/'financial_abstract.csv',index=False,encoding='utf-8-sig')
indicator=ak.stock_financial_analysis_indicator(symbol=symbol)
indicator.to_csv(out/'financial_indicator.csv',index=False,encoding='utf-8-sig')
# These are longer but useful
for name, fn, args in [
 ('balance', ak.stock_balance_sheet_by_report_em, {'symbol':'SZ'+symbol}),
 ('profit', ak.stock_profit_sheet_by_report_em, {'symbol':'SZ'+symbol}),
 ('cashflow', ak.stock_cash_flow_sheet_by_report_em, {'symbol':'SZ'+symbol}),
]:
    try:
        df=fn(**args); df.to_csv(out/f'{name}_em.csv',index=False,encoding='utf-8-sig')
        print(name, df.shape)
    except Exception as e: print(name,'ERR',type(e).__name__,e)

# Convert abstract rows for selected periods
periods=['20260331','20251231','20241231','20231231','20221231','20211231']
metrics=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','销售毛利率','销售净利率','净资产收益率ROE','资产负债率','研发费用','基本每股收益']
rows=[]
for m in metrics:
    rr=abstract[abstract['指标'].astype(str).str.contains(m, regex=False, na=False)]
    if rr.empty:
        print('missing metric',m); continue
    r=rr.iloc[0]
    item={'指标':r['指标']}
    for p in periods:
        val=r.get(p)
        if pd.notna(val): item[p]=float(val) if isinstance(val,(int,float)) else val
    rows.append(item)
print(json.dumps(rows,ensure_ascii=False,indent=2))
(out/'summary_selected.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
# List all metric names for reference
(out/'abstract_metrics.txt').write_text('\n'.join(map(str,abstract['指标'].tolist())),encoding='utf-8')
print('wrote',out)
