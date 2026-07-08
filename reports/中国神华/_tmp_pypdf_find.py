from pypdf import PdfReader
from pathlib import Path
reader=PdfReader('sources/annual2025.pdf')
terms=['董事、高级管理人员持股变动及薪酬情况','董事、高级管理人员薪酬情况','公司董事、高级管理人员','张长岩','宋静刚','王兴中','李新华','股份变动及股东情况','控股股东','实际控制人','关联交易','关连交易','利润分配','股东回报规划','收购杭锦能源','购买资产','发行股份及支付现金购买资产','2026 年度经营目标','资本开支','薪酬','董事会致辞']
for i,p in enumerate(reader.pages):
    text=p.extract_text() or ''
    hits=[t for t in terms if t in text]
    if hits:
        print(f'PAGE {i+1} HITS {hits}')
        for t in hits[:3]:
            idx=text.find(t)
            print(text[max(0,idx-250):idx+900].replace('\n',' ')[:1200])
        print('---')
