import pdfplumber, re
pdf=pdfplumber.open('data/source/siyuan/2025_sustainability_1225117841.PDF')
print('pages', len(pdf.pages))
patterns=['员工','客户满意','客户','供应商','培训','投诉','合规','反贪污','商业道德','安全']
for i,p in enumerate(pdf.pages):
    text=p.extract_text() or ''
    if any(x in text for x in patterns):
        print('\n--- PAGE',i+1,'---')
        # print snippets around first pattern occurrences
        print(text[:3000])