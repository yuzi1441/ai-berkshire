from pathlib import Path
import re
base=Path('sources/cninfo_hmzb')
text=(base/'20260227_2025年年度报告.txt').read_text(encoding='utf-8',errors='ignore')
for pat in ['公司现任董事','主要工作经历','在股东单位任职情况','董事、监事、高级管理人员报酬','报告期内从公司获得的税前报酬','高级管理人员','现任及报告期内离任董事','任职状态','姓名 性别 年龄 职务','有限售条件股份数量','持股变动情况']:
    print(pat, [m.start() for m in re.finditer(re.escape(pat),text)][:10])
# print around all occurrences of 报酬
for m in list(re.finditer('报酬',text))[0:20]:
    print('POS',m.start(), text[m.start()-100:m.start()+250].replace('\n',' '))