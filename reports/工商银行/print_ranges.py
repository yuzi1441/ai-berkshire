from pathlib import Path
text=Path('annual_selected_pages.txt').read_text(encoding='utf-8').splitlines()
for a,b,title in [(130,180,'income'),(250,360,'loan mix'),(360,520,'asset quality'),(520,700,'risk'),(2350,2495,'ecl')]:
    print('\n###',title, a,b)
    for i in range(a-1,min(b,len(text))):
        print(f'{i+1}: {text[i]}')
