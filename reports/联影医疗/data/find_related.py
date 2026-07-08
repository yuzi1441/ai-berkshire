import pdfplumber,pathlib
p=pathlib.Path('data/united_imaging_2025_ar.pdf')
with pdfplumber.open(p) as pdf:
    for term in ['关联方','关联交易','关键管理人员报酬','联影智能']:
        print('\n##',term)
        c=0
        for i,page in enumerate(pdf.pages):
            txt=page.extract_text() or ''
            if term in txt:
                idx=txt.find(term)
                print('P',i+1,txt[max(0,idx-100):idx+400].replace('\n',' | '))
                c+=1
                if c>=8: break
