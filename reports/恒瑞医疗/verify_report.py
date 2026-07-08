from pathlib import Path
p=Path('恒瑞医药投资研究报告.md')
s=p.read_text(encoding='utf-8')
checks=['信息丰富度评级','恒瑞医药','56.77','47.71','40-48','AI 分析置信度','投资确定性']
print('chars',len(s),'missing',[c for c in checks if c not in s])