import yfinance as yf
import pandas as pd
import numpy as np
import Indicators as I
import matplotlib.pyplot as plt
import warnings
from ib_insync import *
import time

## Test how RSI strategy performs against buy/hold

def is_pos(n):
    return n > 0

# options for displaying data
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
np.set_printoptions(suppress=True, formatter={'float': '{:.2f}'.format})
warnings.filterwarnings("ignore")

def RSI_breakout_backtest(ticker,window,year):

    ''' INVERVAL PARAMETERS
    "1m" Max 7 days, only for recent data
    "2m" Max 60 days
    "5m" Max 60 days
    "15m" Max 60 days
    "30m" Max 60 days
    "60m" Max 730 days (~2 years)
    "90m" Max 60 days
    "1d"
    '''
    
    # getting ticker data & intializing vectors for RSI calc
    data = yf.download(ticker, period='3d', interval='1m')
    open = data[["Open"]]
    close = data[["Close"]]
    percents = (close.values - open.values)/open.values
    percents = pd.DataFrame(percents, index = open.index, columns=["% Change"])
    truths = percents.apply(is_pos)
    truths = truths.rename(columns={'% Change': 'isPos'})
    RSIvec = np.ones(len(truths))
 
    # want to calculate rsi for period of 14 days (SEE NOTES)
    for i in range(window,len(percents)):

        possum = 0
        negsum = 0
        poscount = 0
        negcount = 0
    
        recent_percents = percents[0:i+1]
        recent_percents = recent_percents[-window-1:-1]
        recent_truths = truths[0:i+1]
        recent_truths = recent_truths[-window-1:-1]

        for j in range(0,len(recent_truths)):
    
            if recent_truths.iloc[j,0] == True:
                possum += recent_percents.iloc[j]
                poscount += 1

            elif recent_truths.iloc[j,0] == False:
                negsum += recent_percents.iloc[j]
                negcount += 1

        if poscount == 0:
            RSIvec[i] = 0
        elif negcount == 0:
            RSIvec[i] = 100
        else:
            avgain = possum/poscount
            avloss = negsum/negcount
            RSIvec[i] = 100 - 100/(1 - (avgain/avloss))

    RSIvec = pd.DataFrame(RSIvec,index = open.index,columns = ['RSI'])
    comb = pd.concat([open,close,percents,RSIvec], axis=1)
    comb = comb.iloc[window:,:] 

    # backtest, ACCOUNT FOR SLIPPAGE
    P = 0
    alo = comb.iloc[0,0]
    valuevec = alo * np.ones(len(comb))
    actionvec = np.empty(len(comb),object)

    for i in range(1,len(comb)):

        if P == 0 and comb.iloc[i-1,3] < 70: # buy at open
            P = 1
            valuevec[i] = valuevec[i-1] * (1 + comb.iloc[i,2])
            actionvec[i] = 'B'
    
        elif P == 1 and comb.iloc[i-1,3] < 70: # hold
            valuevec[i] = valuevec[i-1] * (1 + comb.iloc[i,2]) * (1 + ((comb.iloc[i,0]-comb.iloc[i-1,1])/comb.iloc[i-1,1]))
            actionvec[i] = 'H'

        elif P == 1 and comb.iloc[i-1,3] >= 70: # sell at open
            P = 0
            valuevec[i] = valuevec[i-1] * (1 + ((comb.iloc[i,0]-comb.iloc[i-1,1])/comb.iloc[i-1,1]))
            actionvec[i] = 'S'
    
        else:
            actionvec[i] = 'N'
            valuevec[i] = valuevec[i-1]

    valuevec = pd.DataFrame(valuevec.round(2),index = comb.index,columns = ['Strat Val'])
    actionvec = pd.DataFrame(actionvec,index = comb.index,columns = ['Action'])
    comb = pd.concat([comb.round(2),valuevec,actionvec], axis=1)
    #print(comb)

    plt.figure()
    plt.plot(comb.index,comb.loc[:,"Strat Val"],label = 'Strategy')
    plt.plot(comb.index,comb.iloc[:,1],label = "Close",color = 'orange')
    plt.xlabel("Timestamp")

    buy_dates = comb[comb["Action"] == "B"].index


    for date in buy_dates:
        shifted_date = comb.index[comb.index.get_loc(date) - 1]  # Shift back by 2
        #plt.axvline(x = shifted_date,color='green')
        #plt.scatter(x=shifted_date, y=comb.loc[date, 4], color='green', marker='x', s=7,zorder= 2)
        plt.scatter(x=shifted_date, y=comb.loc[date, 'Strat Val'], color='green', marker='v', s=7,zorder= 2)

    sell_dates = comb[comb["Action"] == "S"].index

    for date in sell_dates:
        shifted_date = comb.index[comb.index.get_loc(date) - 1]  # Shift back by 2
        #plt.axvline(x = shifted_date,color='red')
        #plt.scatter(x=shifted_date, y=comb.loc[date, ] , color='red', marker='s', s=7,zorder= 2)
        plt.scatter(x=shifted_date, y=comb.loc[date, 'Strat Val'], color='red', marker='v', s=7,zorder= 2)

    plt.ylabel("Value")
    plt.xticks(rotation=30)
    plt.legend()
    plt.title("SMA strategy vs Buy & Hold : {} (S0 = {})".format(ticker,alo.round(2)))
    plt.show()

    pctg = (comb.iloc[len(comb)-1,4]-alo)/alo * 100
    bhpctg = (comb.iloc[len(comb)-1,1]-comb.iloc[0,0])/comb.iloc[0,0] * 100

    text = '\n'.join((
        'Trading Periods : {}'.format(len(comb)),
        'P&L : ${}'.format((comb.iloc[len(comb)-1,4]- alo).round(2)),
        'Growth : {}%'.format(pctg.round(2)),
        'Buy/Hold Growth : {}%'.format(bhpctg.round(2))
    ))


    def slice_by_year(df):
    # Create a dictionary of DataFrames split by year
        year_slices = {
            year: group for year, group in df.groupby(df.index.year)
    }
        return year_slices

    yearly_data = slice_by_year(comb)

    if year == 'all':
        return comb,text
    else:
        return yearly_data[year],text
