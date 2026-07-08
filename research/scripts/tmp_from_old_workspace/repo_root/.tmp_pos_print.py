from pathlib import Path
text=Path('sources/cninfo_hmzb/20260227_2025年年度报告.txt').read_text(encoding='utf-8',errors='ignore')
for start in [34900,36730,39080,39300,66700,7350,12500,14000, 17800, 185000, 188000, 190000]:
    print('\n--- POS',start,'---')
    print(text[start:start+3500].replace('\n',' '))