import subprocess, pathlib, os
root=pathlib.Path(__file__).resolve().parent
fr=root/'tools'/'financial_rigor.py'
cmds=[
 ['cross-validate','--field','revenue_2025','--values','{"annual_report":8377482887.40,"eastmoney":8377482887.40}','--unit','CNY'],
 ['cross-validate','--field','net_profit_2025','--values','{"annual_report":911992429.90,"eastmoney":911992429.90}','--unit','CNY'],
 ['cross-validate','--field','q1_2026_revenue','--values','{"q1_report":1518934346.19,"eastmoney":1518934346.19}','--unit','CNY'],
 ['cross-validate','--field','q1_2026_net_profit','--values','{"q1_report":235825663.52,"eastmoney":235825663.52}','--unit','CNY'],
]
for args in cmds:
 print('\n$', ' '.join(args))
 subprocess.run(['python',str(fr)]+args,check=True)
