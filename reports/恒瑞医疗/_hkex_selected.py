import pdfplumber, os, re
p=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\2026032600033.pdf'
out=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\hkex_annual_selected.txt'
pages=[3,4,5,8,9,10,11,12,13,14,15,16,17,18,19,20,21,45,46,47,48,49,50,69,70,71,72,73,74,75,76,77,78,79,80,94,95,96,97,98,99,100,101]
with pdfplumber.open(p) as pdf, open(out,'w',encoding='utf-8') as f:
    for n in pages:
        txt=pdf.pages[n-1].extract_text() or ''
        f.write(f'\n\n=== PAGE {n} ===\n{txt}')
print(out)
