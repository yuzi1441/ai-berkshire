import akshare as ak, pandas as pd, numpy as np, json

def annual(df):
    d=df.copy()
    d['REPORT_DATE']=pd.to_datetime(d['REPORT_DATE'])
    d=d[d['REPORT_DATE'].dt.strftime('%m-%d')=='12-31'].sort_values('REPORT_DATE')
    return d

profit=annual(ak.stock_profit_sheet_by_report_em(symbol='SZ002226'))
bal=annual(ak.stock_balance_sheet_by_report_em(symbol='SZ002226'))
cf=annual(ak.stock_cash_flow_sheet_by_report_em(symbol='SZ002226'))
fa=ak.stock_financial_abstract(symbol='002226')
cols=['20251231','20241231','20231231','20221231','20211231']
inds=['归母净利润','营业总收入','营业成本','净利润','扣非净利润','经营现金流量净额','净资产收益率(ROE)','总资产报酬率(ROA)','毛利率','销售净利率','资产负债率','流动比率','速动比率','现金比率']
print('### financial_abstract_selected')
for ind in inds:
    row=fa[fa['指标'].eq(ind)].head(1)
    if not row.empty:
        print(ind, {c: row.iloc[0].get(c) for c in cols})
print('\n### statement_selected')
years=[2021,2022,2023,2024,2025]
for y in years:
    pr=profit[profit['REPORT_DATE'].dt.year==y].tail(1)
    ba=bal[bal['REPORT_DATE'].dt.year==y].tail(1)
    ca=cf[cf['REPORT_DATE'].dt.year==y].tail(1)
    def g(df,col):
        if df.empty or col not in df: return None
        v=df.iloc[0][col]
        return None if pd.isna(v) else float(v)
    data={
      'year':y,
      'rev':g(pr,'TOTAL_OPERATE_INCOME'),
      'cost':g(pr,'OPERATE_COST'),
      'parent_np':g(pr,'PARENT_NETPROFIT'),
      'deduct_parent_np':g(pr,'DEDUCT_PARENT_NETPROFIT'),
      'netprofit':g(pr,'NETPROFIT'),
      'ocf':g(ca,'NETCASH_OPERATE'),
      'capex':g(ca,'CONSTRUCT_LONG_ASSET'),
      'fcf': None,
      'cash':g(ba,'MONETARYFUNDS'),
      'total_assets':g(ba,'TOTAL_ASSETS'),
      'total_liab':g(ba,'TOTAL_LIABILITIES'),
      'current_assets':g(ba,'TOTAL_CURRENT_ASSETS'),
      'current_liab':g(ba,'TOTAL_CURRENT_LIAB'),
      'short_loan':g(ba,'SHORT_LOAN'),
      'short_fin_payable':g(ba,'SHORT_FIN_PAYABLE'),
      'noncur_liab_1yr':g(ba,'NONCURRENT_LIAB_1YEAR'),
      'long_loan':g(ba,'LONG_LOAN'),
      'bond_payable':g(ba,'BOND_PAYABLE'),
      'lease_liab':g(ba,'LEASE_LIAB'),
      'parent_equity':g(ba,'TOTAL_PARENT_EQUITY'),
      'total_equity':g(ba,'TOTAL_EQUITY'),
      'share_capital':g(ba,'SHARE_CAPITAL'),
    }
    if data['ocf'] is not None and data['capex'] is not None:
        data['fcf']=data['ocf']-data['capex']
    print(json.dumps(data, ensure_ascii=False))
