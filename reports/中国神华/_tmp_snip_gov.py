from pathlib import Path
text=Path('_extract_governance.txt').read_text(encoding='utf-8')
for kw in ['现任董事、高级管理人员基本情况','董事、高级管理人员持股变动及薪酬情况','董事、高级管理人员薪酬情况','张长岩','宋静刚','康凤伟','李新华','王兴中','王祥喜','持股','薪酬']:
    print('\n###', kw)
    start=0
    c=0
    while True:
        idx=text.find(kw,start)
        if idx<0 or c>=5: break
        print(text[max(0,idx-500):idx+1500].replace('\n',' ')[:2200])
        print('---')
        start=idx+len(kw); c+=1
