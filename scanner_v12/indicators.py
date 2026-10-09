"""A股 V1.2 10项可直接用前复权日线计算的指标。

另有2项VPVR须在固定窗口的分钟/价位成交数据下另行核查，不能用日线推断为已通过。
所有阈值为研究假设，不代表盈利概率。
"""
import numpy as np
import pandas as pd


def calc(df: pd.DataFrame) -> dict:
    df = df.copy().sort_values('date').reset_index(drop=True)
    for x in ('open', 'high', 'low', 'close', 'volume', 'amount'):
        df[x] = pd.to_numeric(df[x], errors='coerce')
    df = df.dropna(subset=['high', 'low', 'close', 'volume'])
    df = df[(df['close'] > 0) & (df['volume'] > 0)].reset_index(drop=True)
    if len(df) < 150:
        raise ValueError('至少需要150个有效交易日用于指标预热和120日窗口')

    hi, lo, cl, vol = (df[x].astype(float) for x in ('high','low','close','volume'))
    prev = cl.shift(1)
    tr = pd.concat([(hi-lo), (hi-prev).abs(), (lo-prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    # Wilder DI / ADX；超过150条有效历史，EWMA预热偏差很小，但应与目标软件校准
    up = hi.diff()
    down = -lo.diff()
    pdm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    plus_di = 100 * pdm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr.replace(0, np.nan)
    minus_di = 100 * mdm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    bbi = sum((cl.rolling(n).mean() for n in (3,6,12,24))) / 4.0
    tp = (hi+lo+cl)/3
    money = tp*vol
    pos = pd.Series(np.where(tp.diff()>0, money, 0.0)).rolling(14).sum()
    neg = pd.Series(np.where(tp.diff()<0, money, 0.0)).rolling(14).sum()
    ratio = pos / neg.replace(0,np.nan)
    mfi = 100-100/(1+ratio)
    mfi = mfi.mask((neg==0)&(pos>0),100).mask((neg==0)&(pos==0),50)
    obv = pd.Series(np.where(cl.diff()>0, vol, np.where(cl.diff()<0, -vol, 0.0)),index=df.index).cumsum()
    # 排除当日：前20日Donchian和OBV高点
    breakout_level = hi.shift(1).rolling(20).max()
    obv_previous_high = obv.shift(1).rolling(20).max()
    price = float(cl.iloc[-1]); br = float(breakout_level.iloc[-1]); bbi_now = float(bbi.iloc[-1]); vol_now = float(vol.iloc[-1]);
    breakout = price/br-1 if br>0 else np.nan
    ratio_bbi = price/bbi_now if bbi_now>0 else np.nan
    atrp = float(atr.iloc[-1])/price*100

    flags = {
        '01_BBI偏离2至8%': 1.02<=ratio_bbi<=1.08,
        '02_BBI连续3日上升': all(bbi.iloc[-i] > bbi.iloc[-i-1] for i in (1,2,3)),
        '03_ADX大于25': float(adx.iloc[-1])>25,
        '04_ADX近3日连续上升': all(adx.iloc[-i]>adx.iloc[-i-1] for i in (1,2,3)),
        '05_MFI60至80且上升': 60<=float(mfi.iloc[-1])<=80 and float(mfi.iloc[-1])>float(mfi.iloc[-4]),
        # 06/07: VPVR不可由此处的日线验证
        '08_突破前20日高点': price>br,
        '09_突破幅度1至5%': 0.01<=breakout<=0.05,
        '10_正DI大于负DI': float(plus_di.iloc[-1])>float(minus_di.iloc[-1]),
        '11_OBV创前20日新高': float(obv.iloc[-1])>float(obv_previous_high.iloc[-1]),
        '12_ATR占比2.5至5%且上升': 2.5<=atrp<=5.0 and float(atr.iloc[-1])>float(atr.iloc[-4]),
    }
    days5 = cl.iloc[-1]/cl.iloc[-6]-1
    # 预警池较宽松，侧重未加速的潜在变化；不构成买入信号
    early = (18<=float(adx.iloc[-1])<=28 and float(adx.iloc[-1])>float(adx.iloc[-4])
             and 50<=float(mfi.iloc[-1])<=75 and float(mfi.iloc[-1])>float(mfi.iloc[-4])
             and (0.92 <= price/br <= 1.05) and days5<=0.15)
    row = {
        '收盘日期': str(df['date'].iloc[-1]), '收盘价': round(price,3),
        '五日涨幅%': round(days5*100,2), '突破位':round(br,3),
        '突破幅度%':round(breakout*100,2), 'BBI':round(bbi_now,3),
        'BBI偏离%':round((ratio_bbi-1)*100,2),'ADX14':round(float(adx.iloc[-1]),2),
        '正DI':round(float(plus_di.iloc[-1]),2),'负DI':round(float(minus_di.iloc[-1]),2),
        'MFI14':round(float(mfi.iloc[-1]),2),'ATR%':round(atrp,2),
        '成交额元':round(float(pd.to_numeric(df['amount'], errors='coerce').iloc[-1]),2),
        '预警池':bool(early),'已核算项通过数':int(sum(flags.values())),
        '已核算项总数':len(flags),'VPVR两项':'未核验',
    }
    return {**row,**flags}
