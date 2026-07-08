from pathlib import Path
text = Path('2025AnnualReportA.txt').read_text(encoding='utf-8')
# write pages around risk sections and financial review snippets
pages = [15,16,17,18,25,26,27,28,29,30,31,32,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,240,241,242,243,244,245,246,247,248]
out=[]
for p in pages:
    marker=f'--- PAGE {p} ---'
    start=text.find(marker)
    if start<0: continue
    end=text.find(f'--- PAGE {p+1} ---', start+1)
    out.append(text[start:end if end!=-1 else len(text)])
Path('annual_selected_pages.txt').write_text('\n'.join(out), encoding='utf-8')
print('wrote annual_selected_pages.txt', len('\n'.join(out)))
