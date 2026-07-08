import pathlib,re,json
src=pathlib.Path('reports/联影医疗/sources')
text=(src/'2025Annual.txt').read_text(encoding='utf-8',errors='ignore')
q1=(src/'2026Q1.txt').read_text(encoding='utf-8',errors='ignore')
# pages dict
def pages(text):
 return re.split(r'---PAGE \d+---', text)
pgs=pages(text); qpgs=pages(q1)
for no in [15,16,95,96,97,98,99,100,101,102,103,108,109,110,111,122,123,124,25,26,27,57,58,59,60]:
 if no < len(pgs):
  print(f'\n===== ANNUAL PAGE {no} =====')
  print(pgs[no][:2500].replace('\n',' '))
for no in [1,2,3,4]:
 if no < len(qpgs):
  print(f'\n===== Q1 PAGE {no} =====')
  print(qpgs[no][:2500].replace('\n',' '))
