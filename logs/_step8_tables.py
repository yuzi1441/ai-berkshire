import re
from pathlib import Path

# Sample step-8 style tables from a few reports
paths = [
    r"E:\ai-berkshire\reports\工业富联\工业富联-investment-team-20260723.md",
    r"E:\ai-berkshire\reports\特变电工\特变电工研究报告-20260713.md",
    r"E:\ai-berkshire\reports\中国神华\中国神华-investment-team-20260714.md",
    r"E:\ai-berkshire\reports\格力电器\格力电器投资研究报告-20260706.md",
    r"E:\ai-berkshire\reports\恒瑞医疗\恒瑞医药-investment-team-20260713.md",
]
for path in paths:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    # find 第八步 or 分层
    lines = text.splitlines()
    print("="*60, p.name)
    for i,l in enumerate(lines):
        if re.search(r"第八步|分层|投资者类型|激进|稳健|保守|行动价格|价格与动作", l) and (l.startswith("#") or "投资者" in l or "类型" in l or "|" in l):
            if i < len(lines)-1:
                print(f"{i+1}:{l[:100]}")
    # print a chunk around 分层
    for i,l in enumerate(lines):
        if re.search(r"分层|投资者类型|激进型", l):
            print("--- chunk ---")
            print("\n".join(lines[i:i+25]))
            break
