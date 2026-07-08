from pathlib import Path
p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\pdf_hits_utf8.txt')
text=p.read_text(encoding='utf-8')
for pat in ['董事、监事和高级管理人员','孙飘扬','戴洪斌','冯佶','刘健俊','薪酬','前十名股东','关联交易','股份回购','现金分红','创新药销售收入','研发投入']:
    i=text.find(pat)
    print('\nPAT',pat,'IDX',i)
    print(text[max(0,i-500):i+1500] if i>=0 else 'not found')
