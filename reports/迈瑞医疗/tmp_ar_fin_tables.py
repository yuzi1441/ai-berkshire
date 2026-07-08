from pathlib import Path
text=Path('ar_text.txt').read_text(encoding='utf-8')
for s,e,label in [(193000,196300,'bs'),(195500,199300,'is'),(199000,202800,'cf'),(110000,116300,'asset_changes'),(132000,136500,'dividend')]:
 print('\n====',label,'====')
 print(text[s:e])
