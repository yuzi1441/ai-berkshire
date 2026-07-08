from pathlib import Path
p=Path('中国神华研究报告-20260707.md')
s=p.read_text(encoding='utf-8')
for key in ['信息丰富度评级：A 级','总市值：9,090.04 亿元','【准出】','中国神华仍是中国最稀缺']:
    print(key, key in s)
print('chars', len(s))
