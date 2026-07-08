import pathlib
p=pathlib.Path(r"C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\长江电力\巴菲特Checklist-长江电力.md")
s=p.read_text(encoding="utf-8")
for k in ["灰色地带", "镜子测试", "27.19", "financial_rigor", "投资第一条规则是不要亏损"]:
    print(k, k in s)
print("chars", len(s))
