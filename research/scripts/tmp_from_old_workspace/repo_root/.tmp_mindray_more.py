from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
for term in ['董事、监事、高级管理人员报酬情况','任职情况','李西廷','徐航','成明和','核心技术人员','前十名股东持股情况','持股5%以上股东','分红','利润分配','现金分红']:
 print('\n###',term)
 idx=text.find(term)
 print(idx)
 if idx!=-1: print(text[idx:idx+2500])
