import pandas as pd, pathlib, json, requests, re, math
base=pathlib.Path('data/oriental_electronics')
absdf=pd.read_csv(base/'financial_abstract_000682.csv')
# collapse duplicate metrics first occurrence
metrics={}
for _,r in absdf.iterrows():
    m=str(r['指标'])
    if m not in metrics: metrics[m]={}
    for c in ['20260331','20251231','20241231','20231231','20221231','20211231']:
        if c in absdf.columns and pd.notna(r[c]) and c not in metrics[m]: metrics[m][c]=float(r[c])
profit=pd.read_csv(base/'profit_em_SZ000682.csv')
bal=pd.read_csv(base/'balance_em_SZ000682.csv')
cf=pd.read_csv(base/'cashflow_em_SZ000682.csv')
def row(df,name): return df[df['REPORT_DATE_NAME'].eq(name)].iloc[0].to_dict()
# quote parse
s=requests.get('https://hq.sinajs.cn/list=sz000682',headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15).content.decode('gb18030','ignore')
sina=re.search(r'"(.*)"',s).group(1).split(',')
t=requests.get('https://qt.gtimg.cn/q=sz000682',headers={'User-Agent':'Mozilla/5.0'},timeout=15).content.decode('gbk','ignore')
tx=re.search(r'"(.*)"',t).group(1).split('~')
price=float(tx[3]); shares=float(tx[73]); mcap_yi=float(tx[45]); pb_dyn=float(tx[46]); pe_dyn=float(tx[39]); total_shares_alt=float(tx[72])
# annual rows
ann=[]
for y in [2021,2022,2023,2024,2025]:
    d=f'{y}1231'
    pr=row(profit,f'{y}年报')
    ba=row(bal,f'{y}年报')
    ca=row(cf,f'{y}年报')
    capex=abs(float(ca.get('CONSTRUCT_LONG_ASSET') or 0)) if 'CONSTRUCT_LONG_ASSET' in ca else None
    ocf=float(metrics['经营现金流量净额'][d])
    fcf=ocf-capex if capex is not None else None
    ann.append({
      'year':y,'revenue':metrics['营业总收入'][d],'np':metrics['归母净利润'][d],'deduct':metrics['扣非净利润'][d],
      'ocf':ocf,'capex':capex,'fcf':fcf,'eps':metrics['基本每股收益'][d],'bps':metrics['每股净资产'][d],
      'roe':metrics.get('净资产收益率ROE',{}).get(d),'roa':metrics.get('总资产报酬率ROA',{}).get(d),
      'gross_margin':metrics.get('销售毛利率',{}).get(d),'net_margin':metrics['销售净利率'][d],
      'debt_ratio':metrics['资产负债率'][d], 'cash':float(ba['MONETARYFUNDS']), 'assets':float(ba['TOTAL_ASSETS']), 'equity':float(ba.get('TOTAL_EQUITY') or 0), 'liab':float(ba['TOTAL_LIABILITIES']),
      'ar':float(ba['ACCOUNTS_RECE']), 'inventory':float(ba['INVENTORY'])
    })
# q1
q1={
 'revenue':metrics['营业总收入']['20260331'], 'np':metrics['归母净利润']['20260331'], 'deduct':metrics['扣非净利润']['20260331'], 'ocf':metrics['经营现金流量净额']['20260331'],
 'cash':row(bal,'2026一季报')['MONETARYFUNDS'], 'ar':row(bal,'2026一季报')['ACCOUNTS_RECE'], 'inventory':row(bal,'2026一季报')['INVENTORY'], 'assets':row(bal,'2026一季报')['TOTAL_ASSETS'], 'liab':row(bal,'2026一季报')['TOTAL_LIABILITIES'],
 'eps':metrics['基本每股收益']['20260331'], 'bps':metrics['每股净资产']['20260331'], 'debt_ratio':metrics['资产负债率']['20260331']
}
# derived
last=ann[-1]
derived={
 'price':price,'sina_price':float(sina[3]),'quote_time_sina':sina[30]+' '+sina[31], 'quote_time_tx':tx[30], 'shares':shares,'mcap_yi':mcap_yi,
 'pe':price/last['eps'],'pb':price/last['bps'],'ps':price/(last['revenue']/shares), 'deduct_pe':(mcap_yi*1e8)/last['deduct'], 'p_fcf':(mcap_yi*1e8)/last['fcf'], 'fcf_yield':last['fcf']/(mcap_yi*1e8), 'dividend':0.05, 'div_yield':0.05/price,
 'revps':last['revenue']/shares,'fcfps':last['fcf']/shares,
 'q1_nonrec':q1['np']-q1['deduct'], 'q1_deduct_ratio':q1['deduct']/q1['np'],
 'ar_rev':last['ar']/last['revenue'], 'inv_rev':last['inventory']/last['revenue'],
 'netcash':last['cash']-2.40e8
}
out={'annual':ann,'q1':q1,'derived':derived}
(base/'team_metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(derived,ensure_ascii=False,indent=2))
