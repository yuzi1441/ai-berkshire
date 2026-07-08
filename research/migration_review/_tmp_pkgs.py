try:
 import akshare as ak
 print('akshare', ak.__version__)
except Exception as e:
 print('NO_AK', repr(e))
try:
 import yfinance as yf
 print('yfinance ok')
except Exception as e:
 print('NO_YF', repr(e))
