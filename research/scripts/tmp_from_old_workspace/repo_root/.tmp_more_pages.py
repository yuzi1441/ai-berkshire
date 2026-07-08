import pdfplumber, pathlib
pdf=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources\siyuan_2025_annual.pdf')
for n in [24,25,26,27,28,29]:
    text=''
    with pdfplumber.open(pdf) as p: text=p.pages[n-1].extract_text() or ''
    pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources', f'annual_p{n:03}.txt').write_text(text,encoding='utf-8')
