import pdfplumber, re, pathlib, sys
for fn in ['sources/1225059012.PDF','sources/1225229244.PDF']:
    print('---',fn)
    pdf=pdfplumber.open(fn)
    print('pages',len(pdf.pages))
    needles=['生命信息与支持','体外诊断','医学影像','营业收入','境外','研发投入','集采','集中带量','迈瑞智检','数智化','客户']
    for i,p in enumerate(pdf.pages):
        text=p.extract_text() or ''
        if any(n in text for n in needles):
            # print selected pages first 1500 chars
            print('\nPAGE',i+1)
            for n in needles:
                if n in text: print('contains',n)
            print(text[:1800].replace('\n',' | '))
            if i>80: break
    pdf.close()
