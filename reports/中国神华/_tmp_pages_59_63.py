from pathlib import Path
text=Path('_extract_governance.txt').read_text(encoding='utf-8')
# Print pages 59-63 from extracted text
for page in range(59,64):
    marker=f'=== PDF_PAGE {page} ==='
    idx=text.find(marker)
    nxt=text.find('=== PDF_PAGE', idx+len(marker)) if idx>=0 else -1
    if idx>=0:
        print(text[idx:nxt if nxt!=-1 else None][:5000])
        print('\n---PAGEEND---\n')
