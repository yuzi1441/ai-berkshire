import subprocess
raw=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','User-Agent: Mozilla/5.0','https://qt.gtimg.cn/q=sz300760'])
text=raw.decode('gbk')
print(text)
fields=text.split('"')[1].split('~')
for i,v in enumerate(fields):
    if i<100:
        print(i, v)
