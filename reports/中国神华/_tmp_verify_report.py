from pathlib import Path
p=Path('中国神华-management-20260707.md')
text=p.read_text(encoding='utf-8')
checks=['中国神华管理层纵深研究','综合评分','段永平','张长岩','宋静刚','79.1%','4.07 / 5.00']
print('path', p.resolve())
print('chars', len(text), 'bytes', p.stat().st_size)
for c in checks:
    print(c, c in text)
print('head:', text[:120].replace('\n',' | '))
