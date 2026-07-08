import pdfplumber, pathlib, json, re
files=list(pathlib.Path('data').glob('*.pdf'))
for f in files:
    try:
        with pdfplumber.open(f) as pdf:
            print('\n===',f.name,'pages',len(pdf.pages),'===')
            for i,page in enumerate(pdf.pages[:3]):
                txt=(page.extract_text() or '').replace('\n',' | ')
                print('P',i+1,txt[:500])
    except Exception as e:
        print('ERR',f,e)
