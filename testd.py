import json
import pandas as pd
import time
import talib
from HuobiDMService import HuobiDM


def Buy(closed,opened,ma5,ma10):

    if ma5[-1] > ma10[-1] and ma5[-2] < ma10[-2]:
        angle = ((ma5[-1] - ma5[-2]) / ma5[-2] + (ma5[-2] - ma5[-3]) / ma5[-3]) * 10000
        kCount = 1
        for i in range(3, 30):
            if (ma5[-i] > ma10[-i]):
                break
            else:
                kCount += 1
        if angle>=8 and kCount>=15 and closed[-1]>opened[-1]:
            return 1

    return 0


with open("test_account_info.json", 'r') as load_f:
    account_info = json.load(load_f)

URL = 'https://www.hbdm.com/'
ACCESS_KEY = ''
SECRET_KEY = ''
count = 0
retryCount =0
while (1):
    try:
        dm = HuobiDM(URL, ACCESS_KEY, SECRET_KEY)
        kline_1min = (dm.get_contract_kline(symbol='BTC_CQ', period='1min'))['data']
    except:
        retryCount += 1
        if(retryCount == 20):
            with open("test_account_info.json", "w") as dump_f:
                json.dump(account_info, dump_f)
            print('connect ws error!')
            break
        continue

    retryCount=0

    kline = (pd.DataFrame.from_dict(kline_1min))[['id', 'close', 'high', 'low', 'open', 'amount']]
    id = kline['id'].values
    id = (id[-1] / 60)
    closed = kline['close'].values
    opened = kline['open'].values
    highed = kline['high'].values
    lowed = kline['low'].values
    amounted = kline['amount'].values
    ma5 = talib.SMA(closed, timeperiod=5)
    ma10 = talib.SMA(closed, timeperiod=10)
    ma60 = talib.SMA(closed, timeperiod=60)
    rsi = talib.RSI(closed, timeperiod=14)
    macd, signal, hist = talib.MACD(closed, fastperiod=12, slowperiod=26, signalperiod=9)

    if (account_info['margin_available'] + account_info['margin_frozen'] +
        (lowed[-1] - account_info['price']) * account_info['volume']) <= 0:
        account_info['margin_available'] = 0
        account_info['margin_frozen'] = 0
        account_info['cost_price'] = 0
        account_info['volume'] =0

    account_info['margin_available'] += (closed[-1] - account_info['price']) * account_info['volume']
    account_info['price'] = closed[-1]

    if (id != account_info['id']):
        position = 0
        position = max(position, Buy(closed, opened, ma5, ma10))
        price = closed[-1] * 1.001

        lowPointLong = min(closed[-1], opened[-1]) - lowed[-1]
        highPointLong = highed[-1] - max(closed[-1], opened[-1])
        lowPointLongRate = lowPointLong / (highed[-1] - lowed[-1])
        highPointLongRate = highPointLong / (highed[-1] - lowed[-1])
        if lowPointLong > 25 and lowPointLongRate > 0.7 and amounted[-1] / amounted[
            -2] > 3 and ma5[-1] < ma60[-1] and highPointLongRate < 0.1 and rsi[-1] < 30:
            position = max(position, 1)

        # buy
        if position > 0 and account_info['margin_available'] > 0:
            margin_available_use = account_info['margin_available'] * position * 20 * (1 - 0.0003)
            volume_add = margin_available_use / price
            account_info['volume'] += volume_add
            account_info['margin_frozen'] += account_info['margin_available'] * position
            account_info['margin_available'] -= account_info['margin_available'] * position
            account_info['cost_price'] = closed[-1]
            account_info['id'] = id

    if account_info['cost_price'] != 0:
        position = 0

        if account_info['cost_price'] != 0 and closed[-1] < account_info['cost_price'] * 0.995:
            position = max(position, 1)

        if rsi[-2] >= 80 and rsi[-2] > rsi[-1]:
            position = max(position, 1)

        if closed[-1] < opened[-1] and amounted[-1] / amounted[-2] >= 6:
            position = max(position, 1)

        if 0 < amounted[-2] / amounted[-3] <= 0.2:
            position = max(position, 1)

        macdSell = 0
        if macd[-1] < signal[-1] and macd[-2] > signal[-2]:
            for i in range(1, 6):
                highPointLong = highed[-i] - max(closed[-i], opened[-i])
                highPointLongRate = highPointLong / (highed[-i] - lowed[-i])
                if highPointLong > 10 and highPointLongRate > 0.6 and rsi[-i] > 70:
                    macdSell = 1
                    break
        if macdSell == 1:
            position = max(position, 1)

        # sell
        if position > 0 and account_info['volume'] > 0:
            account_info['margin_available'] += account_info['margin_frozen'] * position
            account_info['margin_frozen'] -= account_info['margin_frozen'] * position
            account_info['margin_available'] -= account_info['volume'] * position * closed[-1] * 0.001
            account_info['volume'] -= account_info['volume'] * position
            if position == 1:
                account_info['cost_price'] = 0
                account_info['id'] = 0

    count +=1

    if(count%20==0):
        print(account_info['margin_available'] + account_info['margin_frozen'])
    time.sleep(10)
