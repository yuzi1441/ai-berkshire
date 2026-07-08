import pdfplumber, pathlib
for name in ['长江电力第七届董事会第一次会议决议公告_1225384928.pdf','长江电力关于董事会换届选举的公告_1225354351.pdf']:
    pdf=pathlib.Path('data/长江电力')/name
    print('\n===', name, '===')
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            print('\n---PAGE',i,'---')
            print(txt[:5000])
