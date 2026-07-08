from pathlib import Path
text=Path('sources/002028/text/2025AR.txt').read_text(encoding='utf-8')
for page in [37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62]:
    start=text.find(f'--- page {page} ---')
    if start==-1: continue
    end=text.find(f'--- page {page+1} ---', start+1)
    chunk=text[start:end].replace('\n',' ')
    print(f'\n--- PAGE {page} ---')
    print(chunk[:4500])
