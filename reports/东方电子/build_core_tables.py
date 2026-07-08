import pandas as pd, json, math
from pathlib import Path
base=Path('data_snapshots')
# Load
ind=pd.read_csv(base/'em_indicator.csv')
profit=pd.read_csv(base/'em_profit.csv')
bal=pd.read_csv(base/'em_balance.csv')
cash=pd.read_csv(base/'em_cash.csv')
sina=pd.read_csv(base/'sina_indicator.csv')
# Helper annual rows
def annual(df):
    return df[df['REPORT_TYPE'].eq('年报')].copy().sort_values('REPORT_DATE')
# Field lookup
fields={}
for dfname,df in [('profit',profit),('bal',bal),('cash',cash),('ind',ind)]:
    fields[dfname]=list(df.columns)
Path('data_snapshots/columns.json').write_text(json.dumps(fields,ensure_ascii=False,indent=2),encoding='utf-8')
# Compute annual table 2021-2025 from EM
rows=[]
for _,r in annual(ind).query('REPORT_DATE >= "2021-01-01" and REPORT_DATE <= "2025-12-31"').iterrows():
    year=int(str(r['REPORT_DATE'])[:4])
    prow=profit[(profit['REPORT_DATE'].eq(r['REPORT_DATE'])) & (profit['REPORT_TYPE'].eq('年报'))].iloc[0]
    brow=bal[(bal['REPORT_DATE'].eq(r['REPORT_DATE'])) & (bal['REPORT_TYPE'].eq('年报'))].iloc[0]
    crow=cash[(cash['REPORT_DATE'].eq(r['REPORT_DATE'])) & (cash['REPORT_TYPE'].eq('年报'))].iloc[0]
    capex = crow.get('CONSTRUCT_LONG_ASSET', float('nan'))
    ocf = crow.get('NETCASH_OPERATE', float('nan'))
    rows.append({
        'year':year,'date':str(r['REPORT_DATE'])[:10],
        'revenue':r['TOTALOPERATEREVE'], 'parent_np':r['PARENTNETPROFIT'], 'deduct_np':r['KCFJCXSYJLR'],
        'op_profit': prow.get('OPERATE_PROFIT'), 'netprofit': prow.get('NETPROFIT'),
        'ocf': ocf, 'capex': capex, 'fcf': ocf-capex if pd.notna(capex) else float('nan'),
        'roe':r['ROEJQ'], 'roa':r['ZZCJLL'], 'gross_margin':r['XSMLL'], 'net_margin':r['XSJLL'], 'asset_liab':r['ZCFZL'],
        'bps':r['BPS'], 'eps':r['EPSJB'], 'cash':brow.get('MONETARYFUNDS'), 'short_debt':brow.get('SHORT_LOAN'), 'lt_debt':brow.get('LONG_LOAN'), 'lease':brow.get('LEASE_LIAB'), 'current_noncurrent_liab': brow.get('NONCURRENT_LIAB_1YEAR'),
        'total_assets': brow.get('TOTAL_ASSETS'), 'equity_parent': brow.get('TOTAL_PARENT_EQUITY'), 'total_liab': brow.get('TOTAL_LIABILITIES'),
        'shares_est': (r['PARENTNETPROFIT']/r['EPSJB'] if r['EPSJB'] else None),
    })
out=pd.DataFrame(rows).sort_values('year')
out.to_csv('eastmoney_annual_core.csv',index=False,encoding='utf-8-sig')
print(out.to_string(index=False))
# Sina annual rows selected
s=sina[sina['日期'].astype(str).str.endswith('12-31')].copy()
print('\nSINA annual rows')
cols=['日期','加权每股收益(元)','扣除非经常性损益后的每股收益(元)','每股经营性现金流(元)','总资产利润率(%)','营业利润率(%)','销售净利率(%)','销售毛利率(%)','资产负债率(%)','净资产收益率(%)']
print(s[cols].tail(6).to_string(index=False))
