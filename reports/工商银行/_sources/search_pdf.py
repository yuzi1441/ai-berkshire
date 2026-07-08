import pdfplumber, pathlib
for fn in ['_sources/ICBC_2025AnnualReportA.pdf','_sources/ICBC_ESG2025ch.pdf']:
    print('\nFILE',fn)
    with pdfplumber.open(fn) as pdf:
        for pat in ['个人手机银行','手机银行','月活','数字化业务占比','客户数','App']:
            print('---',pat); c=0
            for i,p in enumerate(pdf.pages):
                txt=p.extract_text() or ''
                if pat in txt:
                    s=txt.replace('\n',' '); idx=s.find(pat); print(i+1, s[max(0,idx-180):idx+360]); c+=1
                    if c>=5: break
