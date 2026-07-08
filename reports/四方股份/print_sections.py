from pathlib import Path
s=Path('四方股份2025annual_text.txt').read_text(encoding='utf-8')
for a,b,title in [(280,380,'业务情况'),(380,520,'行业情况'),(520,700,'主要经营情况'),(700,850,'竞争/研发/战略'),(850,972,'计划'),(977,1025,'风险')]:
    lines=s.splitlines()
    print('\n###',title,a,b)
    for i in range(a-1,min(b,len(lines))):
        print(f'{i+1}: {lines[i]}')
