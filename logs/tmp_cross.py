import subprocess, pathlib, os
os.environ['PYTHONIOENCODING']='utf-8'
outdir=pathlib.Path('data/600420')
cmds=[
 ('financial_rigor_cross_revenue.txt',['python','tools/financial_rigor.py','cross-validate','--field','revenue_2025','--values','{"annual_report":93.6307421011,"akshare_eastmoney":93.6307421011}','--unit','亿元']),
 ('financial_rigor_cross_netprofit.txt',['python','tools/financial_rigor.py','cross-validate','--field','net_profit_parent_2025','--values','{"annual_report":9.4160168609,"akshare_eastmoney":9.416017}','--unit','亿元'])
]
for fn,cmd in cmds:
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
    text=p.stdout + p.stderr
    (outdir/fn).write_text(text,encoding='utf-8')
    print(fn, 'rc', p.returncode)
