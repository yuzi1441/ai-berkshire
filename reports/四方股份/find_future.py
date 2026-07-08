from pathlib import Path
s=Path('四方股份2025annual_text.txt').read_text(encoding='utf-8')
idx=s.find('六、公司关于公司未来发展的讨论与分析')
print(idx)
print(s[idx:idx+5000])
