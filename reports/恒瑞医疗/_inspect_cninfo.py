from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\cninfo_recent')
for p in base.rglob('*'):
    if p.is_file() and p.suffix.lower() in ['.json','.txt','.csv','.html']:
        print('FILE',p.name,p.stat().st_size)
        print(p.read_text(encoding='utf-8',errors='ignore')[:2000])
