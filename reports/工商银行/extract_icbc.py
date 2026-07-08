import pdfplumber, re, pathlib
for fn in ['icbc_2025_annual_A.pdf','icbc_2026_q1_A.pdf']:
    path=pathlib.Path(fn)
    print('---',fn)
    with pdfplumber.open(path) as pdf:
        print('pages',len(pdf.pages))
        text='\n'.join((p.extract_text() or '') for p in pdf.pages[:20])
        for pat in ['利息净收入','营业收入','手续费及佣金净收入','客户存款','客户贷款','净利息差','手机银行','个人客户','公司客户','普惠','境内分行']:
            m=re.search(pat,text)
            print(pat, bool(m), (m.start() if m else None))
        print(text[:2000])
