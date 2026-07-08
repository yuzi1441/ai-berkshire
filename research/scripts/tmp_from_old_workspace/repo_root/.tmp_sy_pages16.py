from pathlib import Path
import re
text=Path('sources/002028/text/2025AR.txt').read_text(encoding='utf-8')
# find pages 16-19 specifically without truncating small
for page in [16,17,18,19]:
    start=text.find(f'--- page {page} ---')
    end=text.find(f'--- page {page+1} ---', start+1)
    print(f'\n--- PAGE {page} ---')
    print(text[start:end].replace('\n',' '))
