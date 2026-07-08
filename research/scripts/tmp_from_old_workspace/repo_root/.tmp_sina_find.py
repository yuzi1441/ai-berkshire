import re, pathlib
for name in ['sina_a_page','sina_us_page','sina_hk_page']:
    txt=pathlib.Path(f'sources/sec_beone/{name}.html').read_text(encoding='utf-8')
    print('\n###',name)
    for pat in ['hq_str', 'var hq', 'USStock', 'hk06160', 'sh688235', 'ONC']:
        for m in re.finditer(pat,txt):
            i=m.start(); print('PAT',pat,i, re.sub(r'\s+',' ',txt[i-200:i+600])[:1000]); break
    # script src containing hq
    srcs=re.findall(r'<script[^>]+src="([^"]+)"',txt)
    print([s for s in srcs if 'hq' in s.lower() or 'quote' in s.lower()][:20])