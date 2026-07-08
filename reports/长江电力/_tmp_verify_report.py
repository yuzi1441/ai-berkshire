from pathlib import Path
p=Path('长江电力-business-analyst-商业模式护城河分析-20260707.md')
text=p.read_text(encoding='utf-8')
checks=['business-analyst','商业模式本质','护城河逐项验证','段永平','总体结论','2026H1 发电量','事实与推断边界']
print('chars', len(text))
for c in checks:
    print(c, c in text)
print(text[:500])