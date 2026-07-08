import pdfplumber, pathlib, re, json
for fname in ['ICBC_Q1_2026.pdf','ICBC_AR_2025.pdf','CCB_Q1_2026.pdf','ABC_Q1_2026.pdf','BOC_Q1_2026.pdf','BOCOM_Q1_2026.pdf','PSBC_Q1_2026.pdf','CMB_Q1_2026.pdf']:
    path=pathlib.Path('source_pdfs')/fname
    print('\n---',fname,path.stat().st_size)
    with pdfplumber.open(path) as pdf:
        print('pages',len(pdf.pages))
        text='\n'.join((p.extract_text() or '') for p in pdf.pages[:5])
    for pat in ['营业收入','利息净收入','净息差','不良贷款率','资本充足率','普惠','制造业','科技金融','归属于']:
        m=re.search(pat+'.{0,80}',text)
        if m: print(pat, m.group(0).replace('\n',' | '))
