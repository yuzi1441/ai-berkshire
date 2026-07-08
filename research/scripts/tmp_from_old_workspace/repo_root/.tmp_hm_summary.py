import pandas as pd, pathlib, json, math
base=pathlib.Path('reports/华明装备/sources/eastmoney')
profit=pd.read_csv(base/'profit_em.csv')
bal=pd.read_csv(base/'balance_em.csv')
cf=pd.read_csv(base/'cashflow_em.csv')
periods=['2021年报','2022年报','2023年报','2024年报','2025年报','2026一季报']
rows=[]
for per in periods:
    pr=profit[profit['REPORT_DATE_NAME']==per].iloc[0]
    br=bal[bal['REPORT_DATE_NAME']==per].iloc[0]
    cr=cf[cf['REPORT_DATE_NAME']==per].iloc[0]
    rev=pr['TOTAL_OPERATE_INCOME']; cost=pr['OPERATE_COST']; net=pr['PARENT_NETPROFIT']; deduct=pr['DEDUCT_PARENT_NETPROFIT']; ocf=cr['NETCASH_OPERATE']
    row={
        'period':per,
        'revenue_yi':rev/1e8,
        'gross_margin_pct':(rev-cost)/rev*100 if rev else None,
        'parent_netprofit_yi':net/1e8,
        'deduct_parent_netprofit_yi':deduct/1e8,
        'ocf_yi':ocf/1e8,
        'research_expense_yi':pr.get('RESEARCH_EXPENSE',float('nan'))/1e8,
        'sales_expense_yi':pr.get('SALE_EXPENSE',float('nan'))/1e8,
        'cash_end_yi':br.get('MONETARYFUNDS',float('nan'))/1e8 if 'MONETARYFUNDS' in br else None,
        'total_assets_yi':br.get('TOTAL_ASSETS',float('nan'))/1e8,
        'total_liab_yi':br.get('TOTAL_LIABILITIES',float('nan'))/1e8 if 'TOTAL_LIABILITIES' in br else (br.get('TOTAL_LIAB',float('nan'))/1e8 if 'TOTAL_LIAB' in br else None),
        'equity_parent_yi':br.get('TOTAL_PARENT_EQUITY',float('nan'))/1e8 if 'TOTAL_PARENT_EQUITY' in br else None,
    }
    rows.append(row)
path=pathlib.Path('reports/华明装备/sources/financial_summary_em.json')
path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False,indent=2))
print('balance cols containing money/debt:')
print([c for c in bal.columns if any(t in c.upper() for t in ['MONET','CASH','BORROW','LOAN','BOND','DEBT','LIAB','PAYABLE','NOTE'])][:100])
