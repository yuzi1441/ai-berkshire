from pathlib import Path
text = Path('Announce20260429_5.txt').read_text(encoding='utf-8')
idx=text.find('三、经营情况简析')
print(idx)
print(text[idx-500:idx+3500])
