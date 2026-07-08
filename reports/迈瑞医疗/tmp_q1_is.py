from pathlib import Path
text=Path('q1_text.txt').read_text(encoding='utf-8')
start=text.find('2、合并利润表')
end=text.find('3、合并现金流量表')
print(text[start:end])
