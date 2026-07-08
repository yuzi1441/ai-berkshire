import akshare as ak
import pandas as pd
from pathlib import Path
sym='SZ300760'
outdir=Path('data/mindray'); outdir.mkdir(parents=True, exist_ok=True)
profit=ak.stock_profit_sheet_by_report_em(symbol=sym)
bal=ak.stock_balance_sheet_by_report_em(symbol=sym)
cash=ak.stock_cash_flow_sheet_by_report_em(symbol=sym)
zygc=ak.stock_zygc_em(symbol=sym)
for name,df in [('profit',profit),('balance',bal),('cash',cash),('segment',zygc)]:
    df.to_csv(outdir/f'{name}.csv',index=False,encoding='utf-8-sig')

def pick_year(df):
    return df[(df['REPORT_TYPE']=='年报') & (df['REPORT_DATE_NAME'].isin([f'{y}年报' for y in range(2021,2026)]))].copy()
py=pick_year(profit).sort_values('REPORT_DATE')
by=pick_year(bal).sort_values('REPORT_DATE')
cy=pick_year(cash).sort_values('REPORT_DATE')
rows=[]
for _,p in py.iterrows():
    date=p['REPORT_DATE']; b=by[by['REPORT_DATE']==date].iloc[0]; c=cy[cy['REPORT_DATE']==date].iloc[0]
    revenue=p['TOTAL_OPERATE_INCOME']; np=p['PARENT_NETPROFIT']; dnp=p['DEDUCT_PARENT_NETPROFIT']; gp=revenue-p['OPERATE_COST']
    cfo=c.get('NETCASH_OPERATE'); capex=c.get('CONSTRUCT_LONG_ASSET')
    fcf=cfo-capex if pd.notna(cfo) and pd.notna(capex) else None
    equity=b.get('PARENT_EQUITY') if 'PARENT_EQUITY' in b.index and pd.notna(b.get('PARENT_EQUITY')) else b.get('TOTAL_EQUITY')
    rows.append({
        'year': str(date)[:4], 'revenue_bn': revenue/1e9, 'gross_margin': gp/revenue, 'parent_np_bn': np/1e9, 'deduct_np_bn': dnp/1e9,
        'net_margin': np/revenue, 'cfo_bn': cfo/1e9, 'capex_bn': capex/1e9, 'fcf_bn': fcf/1e9 if fcf is not None else None,
        'total_assets_bn': b['TOTAL_ASSETS']/1e9, 'liabilities_bn': b['TOTAL_LIABILITIES']/1e9, 'debt_ratio': b['TOTAL_LIABILITIES']/b['TOTAL_ASSETS'],
        'cash_bn': b['MONETARYFUNDS']/1e9, 'inventory_bn': b['INVENTORY']/1e9, 'ar_bn': b['ACCOUNTS_RECE']/1e9,
        'eps': p['BASIC_EPS'], 'roe_weighted': None
    })
summary=pd.DataFrame(rows)
for col in ['revenue_bn','parent_np_bn','deduct_np_bn','cfo_bn','fcf_bn']:
    summary[col+'_yoy']=summary[col].pct_change()
summary.to_csv(outdir/'summary_2021_2025.csv',index=False,encoding='utf-8-sig')
print(summary.to_string(index=False,formatters={
 'revenue_bn':'{:.2f}'.format, 'gross_margin':'{:.1%}'.format, 'parent_np_bn':'{:.2f}'.format, 'deduct_np_bn':'{:.2f}'.format, 'net_margin':'{:.1%}'.format,
 'cfo_bn':'{:.2f}'.format, 'capex_bn':'{:.2f}'.format, 'fcf_bn':'{:.2f}'.format, 'total_assets_bn':'{:.2f}'.format,'liabilities_bn':'{:.2f}'.format,'debt_ratio':'{:.1%}'.format,'cash_bn':'{:.2f}'.format,'inventory_bn':'{:.2f}'.format,'ar_bn':'{:.2f}'.format,'eps':'{:.4f}'.format,
 'revenue_bn_yoy':lambda x: '' if pd.isna(x) else f'{x:.1%}', 'parent_np_bn_yoy':lambda x: '' if pd.isna(x) else f'{x:.1%}', 'deduct_np_bn_yoy':lambda x: '' if pd.isna(x) else f'{x:.1%}', 'cfo_bn_yoy':lambda x: '' if pd.isna(x) else f'{x:.1%}', 'fcf_bn_yoy':lambda x: '' if pd.isna(x) else f'{x:.1%}'
}))
# q1 2026
p=profit[profit['REPORT_DATE_NAME']=='2026一季报'].iloc[0]; b=bal[bal['REPORT_DATE_NAME']=='2026一季报'].iloc[0]; c=cash[cash['REPORT_DATE_NAME']=='2026一季报'].iloc[0]
q={'revenue':p['TOTAL_OPERATE_INCOME']/1e9,'parent_np':p['PARENT_NETPROFIT']/1e9,'deduct_np':p['DEDUCT_PARENT_NETPROFIT']/1e9,'cfo':c['NETCASH_OPERATE']/1e9,'cash':b['MONETARYFUNDS']/1e9,'assets':b['TOTAL_ASSETS']/1e9,'liabilities':b['TOTAL_LIABILITIES']/1e9,'inventory':b['INVENTORY']/1e9,'ar':b['ACCOUNTS_RECE']/1e9,'eps':p['BASIC_EPS']}
print('\nQ1 2026', q)
print('\nSegment 2025')
print(zygc[zygc['报告日期'].astype(str).eq('2025-12-31')].to_string(index=False))
