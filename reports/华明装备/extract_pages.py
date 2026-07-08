import pathlib,re
text=pathlib.Path('sources/2025AR_11972985.pdf.txt').read_text(encoding='utf-8',errors='ignore')
def page(n):
    pat=f'===== PAGE {n} ====='
    start=text.find(pat)
    if start<0: return ''
    end=text.find(f'===== PAGE {n+1} =====', start+1)
    return text[start:end if end>=0 else None]
for n in range(11,23):
    pathlib.Path(f'sources/page_{n}.txt').write_text(page(n),encoding='utf-8')
print('pages written')