from pathlib import Path
files=['20250419_2025年员工持股计划（草案）.txt','20260303_关于回购公司股份方案实施完毕暨回购实施结果的公告.txt','20250411_关于2025年度日常关联交易预计的公告.txt','20240601_关于全资子公司对外投资设立印尼子公司的自愿性信息披露公告.txt','20230412_关于对外投资设立新加坡全资子公司的公告.txt','20241231_关于出售参股企业合伙份额暨对外投资的进展公告.txt']
for fn in files:
 p=Path('sources/cninfo_hmzb')/fn
 if not p.exists(): continue
 text=p.read_text(encoding='utf-8',errors='ignore')
 print('\n==',fn,'==')
 for pat in ['购买价格','考核','业绩','解锁','存续期','参加对象','资金来源','回购股份','成交总金额','最高成交价','最低成交价','关联交易','租赁','预计','定价','印尼','投资金额','新加坡','转让价款','12,825.73']:
  pos=text.find(pat)
  if pos!=-1:
   print('\n--',pat,pos,'--')
   print(text[pos-300:pos+1200].replace('\n',' '))