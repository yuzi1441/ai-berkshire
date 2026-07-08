from pathlib import Path
import re
text=Path('2025AnnualReportA.txt').read_text(encoding='utf-8', errors='ignore')
terms=['廖林先生','刘珺先生','执行董事','副董事长','行长','董事长','任职资格','任期','中国工商银行股份有限公司董事长','董事、高级管理人员情况']
for term in terms:
    print('\nTERM',term)
    for m in re.finditer(re.escape(term), text):
        # page number before
        prev=text.rfind('--- PAGE ',0,m.start())
        page='?'
        if prev>=0:
            page=text[prev+9:text.find(' ---',prev+9)]
        s=text[max(0,m.start()-300):m.start()+800]
        print('PAGE',page,'POS',m.start())
        print(s.replace('\n',' ')[:1000])
        break
