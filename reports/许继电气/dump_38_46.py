from pathlib import Path
text=Path('xj_2025_annual_pdftext.txt').read_text(encoding='utf-8')
for want in range(38,47):
    marker=f'--- PAGE {want} ---'
    idx=text.find(marker)
    idx2=text.find(f'--- PAGE {want+1} ---')
    print('\n\n==========',marker,'==========')
    print(text[idx:idx2 if idx2!=-1 else idx+5000])