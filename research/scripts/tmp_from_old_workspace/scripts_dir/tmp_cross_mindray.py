import json, subprocess, sys
pairs=[('2025营业收入', {'巨潮年报':332.82159404,'东方财富/AkShare':332.82159404}, '亿元'),('2025归母净利润',{'巨潮年报':81.35775409,'东方财富/AkShare':81.35775409},'亿元'),('2025经营现金流',{'巨潮年报':101.44968535,'东方财富/AkShare':101.44968535},'亿元'),('2026Q1营业收入',{'巨潮一季报':83.52015912,'东方财富/AkShare':83.52015912},'亿元'),('2026Q1归母净利润',{'巨潮一季报':23.29658005,'东方财富/AkShare':23.29658005},'亿元'),('2025总股本',{'腾讯行情':1212441394,'巨潮年报近似':1212486546},'股')]
for field,vals,unit in pairs:
    cmd=[sys.executable,'tools/financial_rigor.py','cross-validate','--field',field,'--values',json.dumps(vals,ensure_ascii=False),'--unit',unit,'--tolerance','1']
    print('\nCMD',' '.join(cmd[:3]),field)
    subprocess.run(cmd, check=False)
