from pathlib import Path
text=Path('sources/cninfo_hmzb/20260227_2025年年度报告.txt').read_text(encoding='utf-8',errors='ignore')
for start,length in [(36730,6000),(39080,5000),(65800,7000),(171000,21000),(185000,8000),(210000,5000)]:
    print('\n--- POS',start,'---')
    print(text[start:start+length].replace('\n',' '))