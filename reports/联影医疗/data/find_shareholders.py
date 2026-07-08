import pdfplumber, pathlib
p=pathlib.Path('data/united_imaging_2025_ar.pdf')
terms=['控股股东及实际控制人情况','实际控制人','控股股东','普通股股东总数','前十名股东','联影医疗技术集团','上海联和投资']
with pdfplumber.open(p) as pdf:
    for term in terms:
        print('\n##',term)
        cnt=0
        for i,page in enumerate(pdf.pages):
            txt=page.extract_text() or ''
            if term in txt:
                idx=txt.find(term)
                print('P',i+1,txt[max(0,idx-100):idx+350].replace('\n',' | '))
                cnt+=1
                if cnt>=4: break
