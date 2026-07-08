from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
for term in ['Security Ownership of Certain Beneficial Owners', 'The following table sets forth', 'Amgen Inc.', 'Baker Bros. Advisors LP', 'John V. Oyler']:
    idx=text.find(term)
    print('\nTERM',term,idx)
    if idx!=-1: print(text[idx:idx+6000])
