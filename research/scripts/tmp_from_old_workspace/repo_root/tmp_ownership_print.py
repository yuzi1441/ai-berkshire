from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
for idx in [293998,296775,301753]:
    print('\n=== IDX',idx,'===')
    print(text[idx:idx+6000])
