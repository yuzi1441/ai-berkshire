from decimal import Decimal
import subprocess, json, pathlib, requests, re, sys, os
# key numbers
price=Decimal('174.20')
shares=Decimal('782573282')
market_cap_yuan=price*shares
print('market cap yuan',market_cap_yuan,'yi',market_cap_yuan/Decimal('1e8'))
# run rigor commands
cmds=[
 ['python','tools/financial_rigor.py','verify-market-cap','--price',str(price),'--shares',str(shares),'--reported',str(market_cap_yuan),'--currency','CNY'],
 ['python','tools/financial_rigor.py','verify-valuation','--price',str(price),'--eps','4.04','--bvps','19.810869928475','--dividend','0.70','--revenue-per-share',str(Decimal('21539031405.33')/shares)],
 ['python','tools/financial_rigor.py','three-scenario','--price',str(price),'--eps','4.04','--shares',str(shares/Decimal('1e8')),'--growth','0.20','0.12','0.03','--pe','35','28','20','--years','3','--currency','CNY'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2025 revenue','--values','{"Eastmoney":215.3903140533,"Cninfo annual report":215.3903140533}','--unit','亿元'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2025 net profit','--values','{"Eastmoney":31.5014266504,"Cninfo annual report":31.5014266504}','--unit','亿元'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2026Q1 revenue','--values','{"Cninfo Q1 report":45.6866386762,"Eastmoney/filing value":45.6866386762}','--unit','亿元']
]
for c in cmds:
 print('\n$',' '.join(c))
 r=subprocess.run(c,cwd=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire',capture_output=True,text=True,encoding='utf-8')
 print(r.stdout)
 print(r.stderr,file=sys.stderr)
