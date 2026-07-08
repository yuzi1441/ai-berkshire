from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\工商银行')
for name in ['工商银行-earnings-2026Q1.md','工商银行-earnings-2026Q1-研究底稿.md','工商银行-earnings-2026Q1-读者评审.md','工商银行-earnings-2026Q1-李录.md','工商银行-earnings-2026Q1-段永平.md','工商银行-earnings-2026Q1-巴菲特.md','工商银行-earnings-2026Q1-芒格.md']:
    p=base/name
    txt=p.read_text(encoding='utf-8-sig')
    checks=['工商银行','2026Q1']
    ok=all(c in txt for c in checks)
    print(f'{name}\tchars={len(txt)}\tok={ok}\tfirst={txt.splitlines()[0][:60]}')