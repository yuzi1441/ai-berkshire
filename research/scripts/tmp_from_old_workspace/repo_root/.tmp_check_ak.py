try:
 import akshare as ak
 print('akshare', ak.__version__)
except Exception as e: print('no akshare', repr(e))
try:
 import pandas as pd
 print('pandas ok')
except Exception as e: print('no pandas', repr(e))
