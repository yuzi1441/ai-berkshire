try:
 import akshare as ak
 print('akshare', ak.__version__)
except Exception as e:
 print('no akshare',repr(e))
try:
 import pandas as pd
 print('pandas', pd.__version__)
except Exception as e: print('no pandas',e)
try:
 import pdfplumber
 print('pdfplumber ok')
except Exception as e: print('no pdfplumber',e)