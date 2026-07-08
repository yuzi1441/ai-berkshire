import subprocess, json, pathlib, os, sys
root=pathlib.Path.cwd()
outdir=root/'reports'/'沪电股份'
outdir.mkdir(parents=True, exist_ok=True)
py=sys.executable
cmds=[
 ['python','tools/financial_rigor.py','verify-market-cap','--price','128.83','--shares','1924363537','--reported','247915754471.71','--currency','CNY'],
 ['python','tools/financial_rigor.py','verify-valuation','--price','128.83','--eps','1.9875','--bvps','7.853352213044'],
 ['python','tools/financial_rigor.py','three-scenario','--price','128.83','--eps','2.58','--shares','19.24363537','--growth','0.25','0.15','0.02','--pe','45','35','22','--years','3','--currency','CNY'],
 ['python','tools/financial_rigor.py','cross-validate','--field','revenue_2025','--values',json.dumps({'annual_report':18945220585,'eastmoney':18945220585}),'--unit','CNY'],
 ['python','tools/financial_rigor.py','cross-validate','--field','net_profit_2025','--values',json.dumps({'annual_report':3822306272,'eastmoney':3822306272}),'--unit','CNY'],
 ['python','tools/financial_rigor.py','cross-validate','--field','revenue_2026Q1','--values',json.dumps({'q1_report':6214156406,'eastmoney':6214156406}),'--unit','CNY'],
]
parts=[]
for c in cmds:
    res=subprocess.run(c,cwd=root,env={**os.environ,'PYTHONIOENCODING':'utf-8'},text=True,capture_output=True,encoding='utf-8')
    parts.append('$ '+' '.join(c)+'\n')
    parts.append(res.stdout)
    if res.stderr:
        parts.append('\nSTDERR:\n'+res.stderr)
    parts.append('\n'+'='*80+'\n')
    print(c[:3], res.returncode)
text=''.join(parts)
(outdir/'沪电股份-financial-rigor-20260706.txt').write_text(text,encoding='utf-8')
print((outdir/'沪电股份-financial-rigor-20260706.txt').resolve())
