from pathlib import Path
text=Path('source_pdfs/hudian_2025_annual.pdf.selected.txt').read_text(encoding='utf-8')
for kw in ['现金分红','每10股派发现金红利','利润分配预案','以1,924,363,537','每 10 股']:
    idx=text.find(kw)
    print('KW',kw,idx)
    if idx!=-1:
        print(text[max(0,idx-800):idx+1400])
        print('---')
