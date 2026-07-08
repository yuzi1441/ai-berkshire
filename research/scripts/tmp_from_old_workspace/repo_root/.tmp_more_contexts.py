from pathlib import Path
text=Path('data/ar2025_relevant_fullpages.txt').read_text(encoding='utf-8')
for needle in ['前五名客户合计销售金额','前五名供应商合计采购金额','十二、公司可能面临的主要风险','第八节 董事','陈梅芳','李明贵','股份回购','现金分红金额','拟分配现金','泰国全力推动']:
 idx=text.find(needle)
 print('\n###',needle,idx)
 print(text[max(0,idx-1000):idx+2500])
