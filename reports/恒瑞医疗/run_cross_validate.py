import subprocess, sys
cmds=[
 ['python','..\\..\\tools\\financial_rigor.py','cross-validate','--field','2025营业收入','--values','{"年报":31629416193.83,"东方财富":31629416193.83}','--unit','元','sources/rigor_cross_revenue.txt'],
 ['python','..\\..\\tools\\financial_rigor.py','cross-validate','--field','2025归母净利润','--values','{"年报":7711054811.98,"东方财富":7711054811.98}','--unit','元','sources/rigor_cross_profit.txt'],
 ['python','..\\..\\tools\\financial_rigor.py','cross-validate','--field','2026Q1营业收入','--values','{"季报":8140565320.77,"东方财富":8140565320.77}','--unit','元','sources/rigor_cross_q1_revenue.txt'],
]
for cmd in cmds:
    outpath=cmd.pop()
    r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
    open(outpath,'w',encoding='utf-8').write(r.stdout+r.stderr)
    print('---',outpath,'rc',r.returncode,'---')
    print(r.stdout+r.stderr)