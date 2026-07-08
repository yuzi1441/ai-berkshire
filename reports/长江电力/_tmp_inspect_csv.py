import pandas as pd, glob
for f in glob.glob('sources/*.csv'):
    print('\n'+f)
    try:
        df=pd.read_csv(f)
        print(df.shape)
        print(df.head().to_string())
        print(df.columns.tolist()[:50])
    except Exception as e: print('ERR', e)