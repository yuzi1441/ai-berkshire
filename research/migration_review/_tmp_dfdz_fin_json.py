import akshare as ak, pandas as pd, json, pathlib, math, time
symbol='000682'
dates=['20260331','20251231','20241231','20231231','20221231','20211231','20201231']
out={}
for date in dates:
    out[date]={}
    for name,func in [('yjbb',ak.stock_yjbb_em),('lrb',ak.stock_lrb_em),('zcfz',ak.stock_zcfz_em),('xjll',ak.stock_xjll_em)]:
        try:
            df=func(date=date)
            row=df[df['股票代码'].astype(str).str.zfill(6)==symbol]
            rec=row.to_dict('records')
            def clean(v):
                if hasattr(v,'isoformat'): return v.isoformat()
                if isinstance(v,float) and math.isnan(v): return None
                return v
            out[date][name]=[{k:clean(v) for k,v in r.items()} for r in rec]
        except Exception as e:
            out[date][name]={'error':repr(e)}
path=pathlib.Path.cwd()/'source_docs'/'eastmoney_financial_rows_000682.json'
path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(path)
# make compact metrics table
rows=[]
for d,groups in out.items():
    y=(groups.get('yjbb') or [{}])[0] if isinstance(groups.get('yjbb'),list) and groups.get('yjbb') else {}
    b=(groups.get('zcfz') or [{}])[0] if isinstance(groups.get('zcfz'),list) and groups.get('zcfz') else {}
    c=(groups.get('xjll') or [{}])[0] if isinstance(groups.get('xjll'),list) and groups.get('xjll') else {}
    rows.append({
      'date':d,'revenue':y.get('营业总收入-营业总收入'),'net_profit':y.get('净利润-净利润'),'eps':y.get('每股收益'),'roe':y.get('净资产收益率'),'gross_margin':y.get('销售毛利率'),'ocf':c.get('经营性现金流-现金流量净额'),'total_assets':b.get('资产-总资产'),'total_liab':b.get('负债-总负债'),'debt_ratio':b.get('资产负债率'),'equity':b.get('股东权益合计'),'cash':b.get('资产-货币资金'),'inventory':b.get('资产-存货'),'ar':b.get('资产-应收账款')
    })
compact=pathlib.Path.cwd()/'source_docs'/'eastmoney_metrics_000682.csv'
pd.DataFrame(rows).to_csv(compact,index=False,encoding='utf-8-sig')
print(compact)
print(pd.DataFrame(rows).to_string(index=False))
