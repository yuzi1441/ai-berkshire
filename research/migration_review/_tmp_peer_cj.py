import akshare as ak, pandas as pd, re
symbols=['600900','600905','600025','600886']
quotes=open('reports/长江电力/sources/tencent_quotes_20260706.txt',encoding='utf-8').read()
q={}
for sym in symbols:
 m=re.search(r'v_sh%s="([^"]+)"'%sym,quotes); f=m.group(1).split('~')
 q[sym]={'name':f[1],'price':float(f[3]),'market_cap_yi':float(f[45]),'pe_ttm':float(f[39]),'pb':float(f[46]),'div_yield_field':float(f[64]) if f[64] else None,'shares':int(float(f[72]))}
peer=[]
for sym in symbols:
 try:
  df=ak.stock_financial_abstract_ths(symbol=sym, indicator='按报告期')
  r=df[df['报告期']=='2025-12-31'].iloc[0]
  peer.append({**{'code':sym},**q[sym],**{'revenue':r['营业总收入'],'netprofit':r['净利润'],'gross_margin':r['销售毛利率'],'net_margin':r['销售净利率'],'roe':r['净资产收益率'],'debt_asset':r['资产负债率'],'eps':r['基本每股收益'],'bps':r['每股净资产']}})
 except Exception as e:
  print('ERR',sym,e)
out=pd.DataFrame(peer)
print(out.to_string(index=False))
out.to_csv('reports/长江电力/sources/peer_compare.csv',index=False,encoding='utf-8-sig')
