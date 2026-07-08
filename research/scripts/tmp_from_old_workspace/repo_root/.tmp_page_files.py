import pdfplumber, pathlib, json, re
pdf=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources\siyuan_2025_annual.pdf')
for n in [8,9,17,18,19,30,31,37,38,39,40,45,46,62,63,64,65,66,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100]:
    out=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources')/f'annual_p{n:03}.txt'
    with pdfplumber.open(pdf) as p:
        text=p.pages[n-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
    out.write_text(text,encoding='utf-8')
    print(out.name, len(text))
