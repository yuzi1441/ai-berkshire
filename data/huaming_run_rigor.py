import subprocess, json, pathlib, sys
checks = [
 ('revenue_2026Q1', {'cninfo_pdf':530271786.47,'eastmoney':530271786.47}),
 ('net_profit_attr_2026Q1', {'cninfo_pdf':163026548.07,'eastmoney':163026548.07}),
 ('ocf_2026Q1', {'cninfo_pdf':92367764.55,'eastmoney':92367764.55}),
 ('revenue_2025', {'cninfo_pdf':2426794600.12,'eastmoney':2426794600.12}),
 ('net_profit_attr_2025', {'cninfo_pdf':709737360.27,'eastmoney':709737360.27}),
 ('ocf_2025', {'cninfo_pdf':604031442.90,'eastmoney':604031442.90}),
]
out=[]
for field,vals in checks:
    cmd=[sys.executable,'tools/financial_rigor.py','cross-validate','--field',field,'--values',json.dumps(vals),'--unit','元']
    cp=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
    out.append('$ '+' '.join(cmd))
    out.append(cp.stdout)
    if cp.stderr: out.append('STDERR:\n'+cp.stderr)
path=pathlib.Path('data/huaming_002270/financial_rigor_checks.txt')
path.write_text('\n'.join(out),encoding='utf-8')
print(path)
print(path.read_text('utf-8')[:4000])
