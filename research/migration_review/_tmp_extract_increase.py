import pdfplumber, pathlib
for name in ['长江电力关于控股股东增持股份计划的公告_1224556485.pdf','长江电力关于控股股东增持计划进展暨权益变动触及1%刻度的提示性公告_1224859520.pdf']:
 print('\n===',name,'===')
 with pdfplumber.open(pathlib.Path('data/长江电力')/name) as p:
  for i,page in enumerate(p.pages,1):
   txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
   print('\n---P',i,'---')
   print(txt[:3500])
