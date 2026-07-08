import pathlib
p=pathlib.Path('巴菲特Checklist-联影医疗.md')
text=p.read_text(encoding='utf-8')
keys=['联影医疗','灰色地带','安全边际','镜子测试','投资的第一条规则是不要亏损']
for k in keys:
    print(k, 'OK' if k in text else 'MISSING')
print('chars', len(text))
