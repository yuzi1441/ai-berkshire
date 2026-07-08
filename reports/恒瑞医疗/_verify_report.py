from pathlib import Path
p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\恒瑞医药-management-20260706.md')
text=p.read_text(encoding='utf-8')
checks=['数据截止：2026-07-06','综合评分为 **4.2 / 5**','恒瑞医药2025年H股年报','翰森','2026Q1','精确计算工具']
print('exists',p.exists(),'bytes',p.stat().st_size,'chars',len(text))
for c in checks:
    print(c, c in text)
