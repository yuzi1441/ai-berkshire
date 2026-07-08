from pathlib import Path
text=Path('sources/more_sections.txt').read_text(encoding='utf-8').splitlines()
for idx,line in enumerate(text):
    if line.startswith('4000:'):
        print('\n'.join(text[idx:idx+35])); break
