from pathlib import Path
import json, csv, math, re
root=Path('.')
base=Path('sources/联影医疗')
annual=(base/'2025年报.pdf.txt').read_text(encoding='utf-8')
q1=(base/'2026Q1.pdf.txt').read_text(encoding='utf-8')
# Helpers
main=json.load(open('data/uih_RPT_F10_FINANCE_MAINFINADATA.json',encoding='utf-8'))['result']['data']
inc=json.load(open('data/uih_RPT_DMSK_FN_INCOME.json',encoding='utf-8'))['result']['data']
bal=json.load(open('data/uih_RPT_DMSK_FN_BALANCE.json',encoding='utf-8'))['result']['data']
cf=json.load(open('data/uih_RPT_DMSK_FN_CASHFLOW.json',encoding='utf-8'))['result']['data']
def row(data,date):
    return next(d for d in data if d['REPORT_DATE'].startswith(date))
for date in ['2026-03-31','2025-12-31','2024-12-31','2025-03-31']:
    m=row(main,date); i=row(inc,date); b=row(bal,date); c=row(cf,date)
    print('\n##',date,m['REPORT_TYPE'])
    for label,val in [('收入',m.get('TOTALOPERATEREVE')),('归母净利',m.get('PARENTNETPROFIT')),('扣非归母',m.get('KCFJCXSYJLR')),('毛利率%',m.get('XSMLL')),('净利率%',m.get('XSJLL')),('ROE%',m.get('ROEJQ')),('负债率%',m.get('ZCFZL')),('经营现金流',c.get('NETCASH_OPERATE')),('购建长期资产',c.get('CONSTRUCT_LONG_ASSET')),('应收账款',b.get('ACCOUNTS_RECE')),('存货',b.get('INVENTORY')),('货币资金',b.get('MONETARYFUNDS')),('销售费用',i.get('SALE_EXPENSE')),('管理费用',i.get('MANAGE_EXPENSE')),('总资产',b.get('TOTAL_ASSETS')),('总负债',b.get('TOTAL_LIABILITIES'))]:
        if val is not None: print(label, round(val/1e8,4) if abs(val)>100000 else val)
# extract exact tables around revenue segments
snips=[]
for fname,text in [('2025年报',annual),('2026Q1',q1)]:
    for pat in ['六、近三年主要会计数据和财务指标','主营业务分行业、分产品、分地区、分销售模式情况','业务线 2025 年销售设备收入','研发投入','合并利润表','合并现金流量表','合并资产负债表','2025 年销售设备收入','境外收入','前五名客户销售额','行业竞争格局']:
        idx=text.find(pat)
        if idx>=0:
            snips.append(f'\n--- {fname} {pat} @{idx} ---\n'+text[max(0,idx-800):idx+2500])
(base/'key_snippets.txt').write_text('\n'.join(snips),encoding='utf-8')
print('\nwrote', (base/'key_snippets.txt').resolve())
