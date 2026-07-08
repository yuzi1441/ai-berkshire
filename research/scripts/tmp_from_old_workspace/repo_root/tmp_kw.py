from pathlib import Path
files=['annual2025.txt','hkex_application_20260616.txt','q1_2026.txt','related_invest_20260430.txt','vp_appointment.txt','vp_resign.txt','dividend2025.txt']
for file in files:
    text=Path('sources/四方股份/'+file).read_text(encoding='utf-8').splitlines()
    print('\n====',file,'====')
    for kw in ['高秀环','刘志超','杨奇逊','四方电气','控股股东','实际控制人','董事及高级管理层','董事及高級管理層','雇員','员工','僱員','關連交易','关联交易','重大收购','重大收購','2026年','经营计划','經營計劃','总股本','股本','派发现金','每10股','共同投资','副总裁']:
        hits=[(i+1,l.strip()) for i,l in enumerate(text) if kw in l][:8]
        if hits:
            print('--',kw)
            for ln,line in hits: print(f'{ln}: {line[:240]}')
