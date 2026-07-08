from pathlib import Path
text=Path('_extract_business.txt').read_text(encoding='utf-8')
for page in range(13,16):
    marker=f'=== PDF_PAGE {page} ==='
    idx=text.find(marker)
    nxt=text.find('=== PDF_PAGE',idx+len(marker)) if idx>=0 else -1
    print(text[idx:nxt if nxt!=-1 else None][:6000])
    print('\n---PAGEEND---')
