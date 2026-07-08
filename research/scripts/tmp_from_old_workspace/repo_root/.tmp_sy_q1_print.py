import re, json, os
from pathlib import Path
text=Path('sources/002028/text/2026Q1.txt').read_text(encoding='utf-8')
print(text[:6000])
