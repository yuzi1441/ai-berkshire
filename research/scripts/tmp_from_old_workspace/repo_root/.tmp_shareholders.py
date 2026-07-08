from pathlib import Path
text=Path('sources/cninfo_hmzb/20260227_2025年年度报告.txt').read_text(encoding='utf-8',errors='ignore')
for start in [62000,64000,65000,66000]:
 print('\n---',start,'---')
 print(text[start:start+4500].replace('\n',' '))