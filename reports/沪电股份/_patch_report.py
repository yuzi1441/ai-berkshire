from pathlib import Path
p=Path('巴菲特Checklist-沪电股份-20260706.md')
s=p.read_text(encoding='utf-8')
s=s.replace('| 乐观 | 18% | 45x | 3.67 | 164.6 元 | +27.8% |','| 乐观 | 18% | 45x | 3.67 | 165.3 元 | +28.3% |')
p.write_text(s,encoding='utf-8')
print('patched')
