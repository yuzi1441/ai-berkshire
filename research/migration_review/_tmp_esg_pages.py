import pdfplumber, pathlib
pdf=pathlib.Path('data/长江电力/长江电力2024年度环境、社会和治理（ESG）报告_1223421180.pdf')
for rng in [(70,76),(95,103),(104,112)]:
 out=[]
 with pdfplumber.open(pdf) as p:
  for n in range(rng[0],rng[1]+1):
   txt=p.pages[n-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
   out.append(f'\n===== PAGE {n} =====\n{txt}')
 path=pathlib.Path(f'data/长江电力/esg_pages_{rng[0]}_{rng[1]}.txt')
 path.write_text('\n'.join(out),encoding='utf-8')
 print(path, path.stat().st_size)
