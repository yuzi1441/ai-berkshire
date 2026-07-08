from pathlib import Path
text=Path('_tmp_annual2025_full.txt').read_text(encoding='utf-8')
for pg in [151,152,153,154,155,156,157,160,161,162,163,235,236,237,238,239,240]:
 marker=f'===== PAGE {pg} ====='
 i=text.find(marker)
 print('\n'+marker)
 if i!=-1: print(text[i:i+5000])
