import pdfplumber, pathlib
pdf=pathlib.Path('data/长江电力/annual2025.pdf')
with pdfplumber.open(pdf) as p:
    for i,page in enumerate(p.pages,1):
        txt=page.extract_text() or ''
        if '实际控制人' in txt or '国务院国有资产监督管理委员会' in txt:
            idx=max(txt.find('实际控制人'), txt.find('国务院国有资产监督管理委员会'))
            if idx<0: idx=0
            print('P',i,txt[max(0,idx-500):idx+1500].replace('\n',' '))
