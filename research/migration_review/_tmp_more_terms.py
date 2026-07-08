import pdfplumber,re,json
f='reports/工商银行/sources/ICBC_2025_Annual_A.pdf'
terms=['公司金融业务','个人金融业务','金融市场业务','境外及其他','金融科技','科技投入','工小智','数字金融','制造业贷款','普惠贷款','绿色贷款','科技创新贷款','廖林','刘珺','董事长','行长','员工','客户基础']
with pdfplumber.open(f) as pdf:
 for t in terms:
  print('\n### TERM',t)
  n=0
  for i,p in enumerate(pdf.pages):
   text=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
   idx=text.find(t)
   if idx!=-1:
    print('PAGE',i+1, text[max(0,idx-300):idx+900].replace('\n',' | ')[:1300])
    n+=1
    if n>=3: break