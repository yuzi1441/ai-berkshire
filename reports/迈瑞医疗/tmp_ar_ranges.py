from pathlib import Path
text=Path('ar_text.txt').read_text(encoding='utf-8')
for s,e,label in [(93000,105000,'revenue_cost'),(112000,118500,'cash_asset_change'),(160000,170000,'annual_is'),(170000,182000,'annual_bs'),(182000,190000,'annual_cf'),(132000,139000,'dividend'),(275000,281000,'solvency')]:
 print('\n====',label,s,e,'====')
 print(text[s:e])
