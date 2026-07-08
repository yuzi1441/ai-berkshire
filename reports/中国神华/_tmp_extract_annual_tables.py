import pdfplumber
pdf='sources/annual2025.pdf'
pages=[8,9,10,20,21,22,23,25,26,27,28,29,286,287,288,289,290,291,292,293,294,295,296,300,301,302,303,304]
with pdfplumber.open(pdf) as p:
    for pg in pages:
        text=p.pages[pg-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
        print('\n===== PAGE',pg,'=====')
        print(text[:7000])
