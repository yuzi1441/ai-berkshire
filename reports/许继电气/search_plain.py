from pathlib import Path
plain=Path('xj_2025_annual_plain.txt').read_text(encoding='utf-8')
terms=['胡四全','季侃','李俊涛','万桂龙','陆飞','冯宪龙','王廷旭','张旭升','董事、监事、高级管理人员情况','现任及报告期内离任董事','公司高级管理人员','非独立董事','总经理']
for term in terms:
    print('\n====',term,'====')
    start=0; count=0
    while True:
        idx=plain.find(term,start)
        if idx==-1 or count>=4: break
        print('IDX',idx)
        print(plain[max(0,idx-300):idx+700])
        start=idx+len(term); count+=1