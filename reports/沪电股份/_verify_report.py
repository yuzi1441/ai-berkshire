from pathlib import Path
p=Path('巴菲特Checklist-沪电股份-20260706.md')
text=p.read_text(encoding='utf-8')
required=['灰色地带 / 未通过','PE(TTM)：128.83 / 2.2355 ≈ **57.63x**','乐观 | 18% | 45x | 3.67 | 165.3 元 | +28.3%','镜子测试结论：未通过','投资的第一条规则是不要亏损']
for r in required:
    print(r, 'OK' if r in text else 'MISSING')
print('chars',len(text),'lines',text.count('\n')+1)
