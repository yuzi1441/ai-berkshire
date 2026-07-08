from pathlib import Path
p=Path('reports/当前市场投资方向/电网设备-电力自动化-funnel-20260706.md')
print(p.exists(), p)
if p.exists():
    txt=p.read_text(encoding='utf-8')
    idx=txt.find('思源电气')
    print('idx', idx)
    print(txt[max(0,idx-1500):idx+5000])
