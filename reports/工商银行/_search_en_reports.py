from pathlib import Path
import re
terms=['Chairman’s Statement','President’s Statement','Liao Lin','Liu Jun','digital','risk','real economy','dividend','capital management','five transformations','GBC+','AI+','technology finance','inclusive finance','manufacturing','NPL ratio','capital adequacy ratio']
for txtp in sorted(Path('sources').glob('ICBC_*_AnnualReport_EN.pdf.txt')):
    text=txtp.read_text(encoding='utf-8', errors='ignore')
    print('\n###',txtp.name, len(text))
    for term in terms:
        m=re.search(re.escape(term), text, re.I)
        if m:
            prev=text.rfind('--- PAGE ',0,m.start())
            page='?'
            if prev>=0: page=text[prev+9:text.find(' ---',prev+9)]
            print(term,'PAGE',page,'POS',m.start())
