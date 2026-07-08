from pathlib import Path
text=Path('sources/长江电力/cypc_2025_annual.pdf.txt').read_text(encoding='utf-8')
for pat in ['国家电网有限公司','中国南方电网有限责任公司','前五名客户','可再生能源装机','全国水电装机容量','全国统一电力市场','绿色环境价值','容量价值','电能量价值','2026 年，公司六座梯级电站力争实现年发电量']:
 print('\n###',pat)
 i=text.find(pat)
 print(i, text[i-500:i+900].replace('\n',' | ') if i>=0 else '')
