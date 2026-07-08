from pathlib import Path
from pypdf import PdfReader
base=Path('sources/cninfo_hmzb')
files=['20250411_2024年年度报告.pdf','20260227_2025年年度报告.pdf','20260427_2026年一季度报告.pdf','20260227_关于2025年度利润分配预案的公告.pdf','20251027_关于2025年第三季度利润分配预案的公告.pdf','20250808_关于2025年半年度利润分配预案的公告.pdf','20260303_关于回购公司股份方案实施完毕暨回购实施结果的公告.pdf','20250419_2025年员工持股计划（草案）.pdf','20250411_关于2025年度日常关联交易预计的公告.pdf']
for name in files:
    p=base/name; txtp=p.with_suffix('.txt')
    print('FILE',name,p.exists())
    if not p.exists(): continue
    try:
        reader=PdfReader(str(p))
        parts=[]
        for i,page in enumerate(reader.pages):
            try: parts.append(page.extract_text() or '')
            except Exception as e: parts.append(f'\n[PAGE {i} ERR {e}]\n')
        text='\n'.join(parts)
        txtp.write_text(text,encoding='utf-8')
        print('pages',len(reader.pages),'chars',len(text))
    except Exception as e:
        print('ERR',e)