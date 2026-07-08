import pdfplumber, pathlib
pdf='sources/annual2025.pdf'
pages=[8,9,10,20,21,22,23,25,26,27,28,29,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255,256,257,258,259,260,261,262,263,264,265,266,267,268,269,270,271,272,273,274,275,276,277,278,279,280,281,282,283,284,285,286,287,288,289,290,291,292,293,294,295,296,300,301,302,303,304]
parts=[]
with pdfplumber.open(pdf) as p:
    for pg in pages:
        text=p.pages[pg-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
        parts.append(f'\n===== PAGE {pg} =====\n{text[:9000]}')
path=pathlib.Path('_tmp_annual_pages_utf8.txt')
path.write_text('\n'.join(parts), encoding='utf-8')
print(path.resolve(), path.stat().st_size)
