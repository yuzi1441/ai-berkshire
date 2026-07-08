from pathlib import Path
text=Path('_1228703140703055873.html').read_text(encoding='utf-8')
for pos in [78000, 98500, 98900, 99100, 116500]:
 print('\n---pos',pos,'---')
 print(text[pos:pos+1600])