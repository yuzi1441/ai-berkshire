import subprocess, json
items=[
('revenue_2025',{'cninfo_annual_report':2426794600.12,'akshare_eastmoney':2426794600.12},'元'),
('net_profit_2025',{'cninfo_annual_report':709737360.27,'akshare_eastmoney':709737360.27},'元'),
('operating_cash_flow_2025',{'cninfo_annual_report':604031442.90,'akshare_eastmoney':604031442.90},'元'),
('q1_revenue_2026',{'cninfo_q1_report':530271786.47,'akshare_eastmoney':530271800.00},'元'),
]
for field, values, unit in items:
    print('\nRUN',field)
    subprocess.run(['python','tools/financial_rigor.py','cross-validate','--field',field,'--values',json.dumps(values),'--unit',unit],check=False)