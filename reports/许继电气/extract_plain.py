from bs4 import BeautifulSoup
from pathlib import Path
text=Path('sina_xj_2025.html').read_bytes().decode('gbk','ignore')
soup=BeautifulSoup(text,'html.parser')
plain=soup.get_text('\n')
# Save plain for search
Path('xj_2025_annual_plain.txt').write_text(plain,encoding='utf-8')
print('plain len',len(plain),'tables',len(soup.find_all('table')))
# print snippets by terms clean
for term in ['第四节公司治理', '董事、监事和高级管理人员情况', '任职情况', '董事、监事、高级管理人员报酬情况', '公司实际控制人及其一致行动人', '前10名股东持股情况', '关联交易', '承诺事项履行情况', '利润分配', '现金分红', '控股股东']:
    idx=plain.find(term)
    print('\n====',term,idx,'====')
    if idx!=-1:
        print(plain[idx:idx+2000])