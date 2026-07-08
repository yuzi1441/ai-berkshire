import pdfplumber
p=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\hengrui_2026_q1.pdf'
with pdfplumber.open(p) as pdf:
    for i in range(len(pdf.pages)):
        txt=pdf.pages[i].extract_text() or ''
        print('\n=== PAGE',i+1,'===')
        print(txt[:2500])
