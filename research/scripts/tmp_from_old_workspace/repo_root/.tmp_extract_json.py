import json,pathlib
root=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources')
for fn in ['RPT_DMSK_FN_BALANCE.json','RPT_DMSK_FN_INCOME.json','RPT_DMSK_FN_CASHFLOW.json']:
    data=json.loads((root/fn).read_text(encoding='utf-8'))
    print('---',fn)
    for r in data[:8]:
        print(r.get('REPORT_DATE'), r.get('DATE_TYPE_CODE'), r.get('REPORT_TYPE_CODE'), 'rev',r.get('TOTAL_OPERATE_INCOME'), 'np',r.get('PARENT_NETPROFIT'), 'opcf',r.get('NETCASH_OPERATE'), 'capex',r.get('CONSTRUCT_LONG_ASSET'), 'assets',r.get('TOTAL_ASSETS'), 'liab',r.get('TOTAL_LIABILITIES'), 'cash',r.get('MONETARYFUNDS'))
