from pathlib import Path
text=Path('source_pdfs/hudian_2025_annual.pdf.selected.txt').read_text(encoding='utf-8')
for kw in ['实际控制人','控股股东','董事长','总经理','陈梅芳','吴传彬','吴礼淦','股份数量','董事、监事、高级管理人员报酬']:
    print('\nKW',kw)
    start=0; c=0
    while True:
        idx=text.find(kw,start)
        if idx==-1 or c>=3: break
        print('idx',idx)
        print(text[max(0,idx-500):idx+1600])
        print('---')
        start=idx+len(kw); c+=1
