from pathlib import Path
text = Path('Announce20260429_5.txt').read_text(encoding='utf-8')
for page in range(1,8):
    marker=f'--- PAGE {page} ---'
    start=text.find(marker)
    end=text.find(f'--- PAGE {page+1} ---', start+1)
    print('\n'+'='*20, 'PAGE', page, '='*20)
    print(text[start:end][:5000])
