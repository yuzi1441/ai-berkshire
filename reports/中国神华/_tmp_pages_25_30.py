from pathlib import Path
text=Path('_extract_business.txt').read_text(encoding='utf-8')
for page in range(25,31):
 idx=text.find(f'=== PDF_PAGE {page} ===')
 nxt=text.find('=== PDF_PAGE', idx+5) if idx>=0 else -1
 if idx>=0:
  print(text[idx:nxt if nxt!=-1 else None][:6500])
  print('\n---')
