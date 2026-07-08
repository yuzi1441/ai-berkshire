from pathlib import Path
text=Path('extracted_pages.txt').read_text(encoding='utf-8')
for term in ['拟每10股派发现金股息','每10股','派发现金股息','601.97','503.96','利润分配方案','现金分红约']:
    print('\nTERM',term)
    idx=0; c=0
    while True:
        idx=text.find(term,idx)
        if idx==-1: break
        c+=1
        print(text[max(0,idx-300):idx+500].replace('\n',' '))
        idx+=len(term)
        if c>=5: break