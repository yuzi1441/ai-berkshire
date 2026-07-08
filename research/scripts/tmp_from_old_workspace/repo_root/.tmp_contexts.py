from pathlib import Path
text=Path('data/ar2025_relevant_fullpages.txt').read_text(encoding='utf-8')
for needle in ['分行业','数据通讯应用领域PCB','2024-2029年数据通讯','智能汽车应用领域','前五名客户','研发投入金额','公司研发人员情况','2025年公司先后荣获','十二、公司可能面临','现金分红','董事、监事和高级管理人员']:
    idx=text.find(needle)
    print('\n###',needle,idx)
    print(text[max(0,idx-800):idx+2000])
