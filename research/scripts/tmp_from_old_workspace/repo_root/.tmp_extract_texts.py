from pathlib import Path
import pdfplumber, re
base=Path('sources/cninfo_hmzb')
for p in base.glob('*.pdf'):
    if any(k in p.name for k in ['年度报告','一季度报告','利润分配预案','回购公司股份方案实施完毕','员工持股计划（草案）','日常关联交易预计','对外投资设立新加坡','印尼子公司','出售参股企业']):
        txtp=p.with_suffix('.txt')
        if txtp.exists() and txtp.stat().st_size>1000: continue
        try:
            with pdfplumber.open(p) as pdf:
                text='\n'.join((page.extract_text(x_tolerance=1,y_tolerance=3) or '') for page in pdf.pages)
            txtp.write_text(text,encoding='utf-8')
            print('TXT',p.name,len(text))
        except Exception as e:
            print('ERR',p.name,e)