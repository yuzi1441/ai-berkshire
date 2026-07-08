import subprocess
codes=['sz300760','sh688271','sz300832','sh603658','sz002223','sz300633','sh688617']
for code in codes:
    raw=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','User-Agent: Mozilla/5.0',f'https://qt.gtimg.cn/q={code}'])
    text=raw.decode('gbk')
    fields=text.split('"')[1].split('~') if '"' in text else []
    if len(fields)>46:
        print(code, fields[1], 'price', fields[3], 'chg%', fields[32], 'PE', fields[39], 'mktcap_yi', fields[45], 'PB', fields[46], 'date', fields[30])
