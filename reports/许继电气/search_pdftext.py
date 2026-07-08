from pathlib import Path
text=Path('xj_2025_annual_pdftext.txt').read_text(encoding='utf-8')
for term in ['四、董事和高级管理人员情况','董事、监事、高级管理人员报酬情况','董事会报告','董事会成员', '任职情况', '高级管理人员', '报告期内董事和高级管理人员报酬情况', '公司实际控制人', '前十名股东', '关联交易', '日常关联交易', '利润分配']:
    print('\n====',term,'====')
    idx=text.find(term)
    print(idx)
    if idx!=-1: print(text[idx:idx+3000])