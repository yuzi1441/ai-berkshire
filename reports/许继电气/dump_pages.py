from pathlib import Path
text=Path('xj_2025_annual_pdftext.txt').read_text(encoding='utf-8')
# split pages
pages=text.split('\n\n--- PAGE ')
for want in [8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,36,37,38,39,40,41,42,43,44,45,46,55,56,57,58,59,60,61,62,63,68,69,70,71,72,73,74,75,76,77,78,79]:
    marker=f'{want} ---'
    for chunk in pages:
        if chunk.startswith(marker):
            print('\n\n========== PAGE',want,'==========')
            print(chunk[:4000])
            break