from pathlib import Path
text=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\annual_selected_pages.txt').read_text(encoding='utf-8')
def page(n):
    marker=f'=== PAGE {n} ==='
    i=text.find(marker)
    j=text.find('=== PAGE ', i+5)
    return text[i:j if j!=-1 else None]
for n in [97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,121,122,123,124,125,126,127]:
    p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗')/f'annual_p{n}.txt'
    p.write_text(page(n),encoding='utf-8')
    print(n, len(page(n)))
