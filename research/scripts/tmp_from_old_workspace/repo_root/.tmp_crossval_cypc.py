import subprocess, sys, json
cmds=[
['python','tools/financial_rigor.py','cross-validate','--field','2025营业收入','--values',json.dumps({'公司年报':862.419402222,'新浪财经':862.42,'东方财富AKShare':862.4194},ensure_ascii=False),'--unit','亿元'],
['python','tools/financial_rigor.py','cross-validate','--field','2025归母净利润','--values',json.dumps({'公司年报':345.028091764,'新浪财经':345.03,'东方财富AKShare':345.0281},ensure_ascii=False),'--unit','亿元'],
['python','tools/financial_rigor.py','cross-validate','--field','2026Q1归母净利润','--values',json.dumps({'公司一季报':67.610068985,'智通/财报摘要':67.61,'东方财富AKShare':67.6101},ensure_ascii=False),'--unit','亿元'],
]
for c in cmds:
 print('\n$', ' '.join(c[:4]), '...')
 subprocess.run(c, check=True)
