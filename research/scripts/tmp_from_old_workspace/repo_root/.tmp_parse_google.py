import re, json, pathlib
for name in ['google','googlehk','googleus']:
    txt=pathlib.Path(f'sources/sec_beone/{name}_quote_raw.txt').read_text(encoding='utf-8',errors='ignore')
    print('\n###',name)
    for pat in ['data-last-price','YMlKec','Market cap','Previous close','BeOne','百济']:
        i=txt.find(pat)
        print(pat,i)
        if i!=-1: print(txt[i-300:i+500].replace('\n',' ')[:1000])
    # regex around class YMlKec
    vals=re.findall(r'<div class="YMlKec fxKbKc">([^<]+)</div>', txt)
    print('YM vals', vals[:10])
    mc=re.findall(r'Market cap.*?P6K39c">([^<]+)', txt, flags=re.S)
    print('mc', mc[:5])