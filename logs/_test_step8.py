import sys, re
from pathlib import Path
sys.path.insert(0, r"E:\ai-berkshire\tools")
import importlib
import build_investment_dashboard as d
importlib.reload(d)

paths = [
    r"E:\ai-berkshire\reports\工业富联\工业富联-investment-team-20260723.md",
    r"E:\ai-berkshire\reports\特变电工\特变电工研究报告-20260713.md",
    r"E:\ai-berkshire\reports\特变电工\特变电工-investment-team-20260713.md",
    r"E:\ai-berkshire\reports\中国神华\中国神华-investment-team-20260714.md",
    r"E:\ai-berkshire\reports\腾讯\腾讯控股研究报告-20260722.md",
    r"E:\ai-berkshire\reports\恒瑞医疗\恒瑞医药-investment-team-20260713.md",
]
for path in paths:
    p = Path(path)
    if not p.exists():
        print("MISSING", path); continue
    lines = p.read_text(encoding="utf-8").splitlines()
    heads = [(i+1,l) for i,l in enumerate(lines) if re.match(r"^#{1,3}\s+", l) and re.search(r"估值|决策|行动|建议|第八|第七", l)]
    vs = d.extract_valuation_section(lines)
    print("="*60)
    print(p.name)
    print(" file heads:")
    for h in heads[:12]:
        print("  ", h[0], h[1][:70])
    if not vs:
        print("  EXTRACT NONE"); continue
    print(f" extract: {vs['start_line']}-{vs['end_line']} | {vs['heading']}")
    for line in vs["markdown"].splitlines():
        if line.startswith("#"):
            print("   ", line[:80])
    print("  has 第八步/最终决策:", bool(re.search(r"第八步|最终决策|行动清单", vs["markdown"])))
