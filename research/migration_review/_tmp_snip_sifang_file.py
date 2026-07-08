from pathlib import Path
text=Path('data/raw/sifang/annual.txt').read_text(encoding='utf-8')
patterns=['主营业务分行业','主营业务分产品','分产品情况说明','公司业务概要','报告期内公司所处行业情况','主要业务','研发投入','货币资金','应收账款','存货','负债合计','利润分配','前10名股东','董事、监事、高级管理人员']
out=[]
for pat in patterns:
 out.append('\n==== '+pat+' ====')
 start=0; count=0
 while count<3:
  idx=text.find(pat,start)
  if idx<0: break
  out.append(f'idx {idx}')
  out.append(text[max(0,idx-500):idx+1800])
  start=idx+len(pat); count+=1
Path('data/raw/sifang/key_snips.txt').write_text('\n'.join(out),encoding='utf-8')
print(Path('data/raw/sifang/key_snips.txt').resolve())