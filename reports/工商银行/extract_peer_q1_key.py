import pdfplumber, pathlib, re, json
banks=['ICBC','CCB','ABC','BOC','BOCOM','PSBC','CMB']
for b in banks:
    path=pathlib.Path('source_pdfs')/f'{b}_Q1_2026.pdf'
    print('\n###',b)
    with pdfplumber.open(path) as pdf:
        text='\n'.join((p.extract_text() or '') for p in pdf.pages)
    for pat in ['营业收入','利息净收入','归属于.*?净利润','净息差','净利息收益率','年化净利息收益率','不良贷款率','拨备覆盖率','客户贷款及垫款总额','发放贷款和垫款总额','客户贷款及垫款','资本充足率']:
        print('--',pat)
        for m in re.finditer(pat+'.{0,120}',text):
            s=m.group(0).replace('\n',' | ')
            print(s[:220])
            break
