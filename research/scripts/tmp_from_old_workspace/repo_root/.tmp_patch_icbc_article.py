from pathlib import Path
p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\工商银行\工商银行-earnings-2026Q1.md')
text=p.read_text(encoding='utf-8')
text=text.replace('**最新财报：2026 年第一季度报告；背景：2025 年报**  ', '**最新财报：二零二六年第一季度报告；背景：二零二五年报**  ')
p.write_text(text,encoding='utf-8')