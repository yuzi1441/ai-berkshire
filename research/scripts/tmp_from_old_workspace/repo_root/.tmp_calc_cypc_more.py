from decimal import Decimal
vals={
'rev2020':Decimal('577.8337'),'rev2025':Decimal('862.4194'),'np2020':Decimal('262.9789'),'np2025':Decimal('345.0281'),
'ocf2025':Decimal('605.6293'),'capex2025':Decimal('184.8847'),'shares':Decimal('244.68217716'),
'price':Decimal('27.19'),'market_cap_yi':Decimal('6652.91'),'netdebt':Decimal('0')}
for k,v in vals.items(): pass
rev_cagr=(vals['rev2025']/vals['rev2020'])**(Decimal(1)/Decimal(5))-1
np_cagr=(vals['np2025']/vals['np2020'])**(Decimal(1)/Decimal(5))-1
fcf=vals['ocf2025']-vals['capex2025']
print('rev_cagr', rev_cagr, 'np_cagr',np_cagr,'fcf_yi',fcf,'fcf_per_share',fcf/vals['shares'])
print('eps_ttm', Decimal('1.4101')+Decimal('0.2763')-Decimal('0.2117'))
print('div_yield', Decimal('1.21')/vals['price'])
print('fcf_yield', fcf/vals['market_cap_yi'])
# Re-run tools and save to file combined outputs
import subprocess, json, pathlib
cmds=[
['python','tools/financial_rigor.py','verify-market-cap','--price','27.19','--shares','24468217716','--reported','665291000000','--currency','CNY'],
['python','tools/financial_rigor.py','verify-valuation','--price','27.19','--eps','1.4746','--bvps','9.3130','--dividend','1.21','--fcf-per-share','1.7192','--revenue-per-share','3.5246'],
['python','tools/financial_rigor.py','three-scenario','--price','27.19','--eps','1.4746','--shares','244.68217716','--growth','0.04','0.02','-0.02','--pe','21','18','15','--years','5','--currency','CNY'],
['python','tools/financial_rigor.py','cross-validate','--field','2025营业收入','--values',json.dumps({'公司年报':862.419402222,'新浪财经':862.42,'东方财富AKShare':862.4194},ensure_ascii=False),'--unit','亿元'],
['python','tools/financial_rigor.py','cross-validate','--field','2025归母净利润','--values',json.dumps({'公司年报':345.028091764,'新浪财经':345.03,'东方财富AKShare':345.0281},ensure_ascii=False),'--unit','亿元'],
['python','tools/financial_rigor.py','cross-validate','--field','2026Q1归母净利润','--values',json.dumps({'公司一季报':67.610068985,'东方财富AKShare':67.6101,'媒体财报摘要':67.61},ensure_ascii=False),'--unit','亿元'],
]
out=[]
for c in cmds:
    res=subprocess.run(c, capture_output=True, text=True, encoding='utf-8')
    out.append('$ '+' '.join(c[:4])+' ...\n'+res.stdout+res.stderr)
pathlib.Path('sources/长江电力/financial_rigor_outputs.txt').write_text('\n\n'.join(out),encoding='utf-8')
print('saved outputs')
