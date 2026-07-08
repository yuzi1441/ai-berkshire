import pdfplumber, pathlib
p=pathlib.Path('sources/huaming/1224986242_2025年年度报告.PDF')
with pdfplumber.open(p) as pdf:
    for i,page in enumerate(pdf.pages):
        text=page.extract_text() or ''
        if '十一、公司未来发展的展望' in text or '可能面对的风险' in text or '风险' in text and i<40:
            print('PAGE', i+1)
            print(text[:5000])
