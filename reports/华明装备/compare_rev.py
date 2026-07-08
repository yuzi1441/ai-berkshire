import pathlib,re
for fname in ['sources/2024AR_10862534.pdf.txt','sources/2025AR_11972985.pdf.txt']:
    text=pathlib.Path(fname).read_text(encoding='utf-8',errors='ignore')
    print('\nFILE',fname)
    for p in ['电力设备','数控设备','电力工程','营业收入构成']:
        m=re.search(p,text)
    # find table snippet around 营业收入构成
    idx=text.find('营业收入构成')
    print(text[idx:idx+1800].replace('\n',' ') if idx!=-1 else 'no')