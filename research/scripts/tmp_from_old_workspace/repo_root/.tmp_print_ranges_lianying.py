from pathlib import Path
text=Path('sources/联影医疗/lianying_annual_20260429_1225233728.pdf.pypdf.txt').read_text(encoding='utf-8')
for start,end in [(104000,114000),(121500,126500),(126000,132500),(145000,153000),(180000,188500),(220000,225500)]:
    print('\n\n===== RANGE',start,end,'=====')
    print(text[start:end])
