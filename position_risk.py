"""V1.2 价格位置风险闸门（不参与原10项技术评分）。

日线前复权口径与扫描器保持一致；风险阈值仅为待回测的经验预警。
任何未知项不能被解读为已通过；任何结果不构成可买入结论。
"""
import numpy as np
import pandas as pd


def assess_position(df: pd.DataFrame) -> dict:
    x = df.copy().sort_values('date').reset_index(drop=True)
    for k in ('open', 'high', 'low', 'close'):
        x[k] = pd.to_numeric(x[k], errors='coerce')
    x = x.dropna(subset=['open', 'high', 'low', 'close'])
    x = x[(x['close'] > 0) & (x['high'] >= x['low'])].reset_index(drop=True)
    if len(x) < 62:
        raise ValueError('位置风险检查需要至少62个有效交易日')

    close = x['close']
    cur = float(close.iloc[-1])
    ret20 = (cur / float(close.iloc[-21]) - 1) * 100
    ret60 = (cur / float(close.iloc[-61]) - 1) * 100

    # 年初至今必须以“上一自然年最后一个有效交易日的收盘”为基准。
    # 未抓到年末基准时是未知，而不是涨幅0%。
    current_year = str(x['date'].iloc[-1])[:4]
    before_year = x[x['date'].astype(str).str[:4] < current_year]
    ytd = (cur / float(before_year['close'].iloc[-1]) - 1) * 100 if not before_year.empty else np.nan

    # 52周高点排除当日，避免用当天高点替代历史突破参照。
    # 未满252个历史交易日，标记未知，不伪造52周数据。
    previous_52_high = float(x['high'].iloc[-253:-1].max()) if len(x) >= 253 else np.nan
    from_high = (cur / previous_52_high - 1) * 100 if np.isfinite(previous_52_high) else np.nan
    today_high = float(x['high'].iloc[-1]); today_low = float(x['low'].iloc[-1])
    today_open = float(x['open'].iloc[-1])
    day_range = today_high - today_low
    upper_ratio = max(0.0, today_high - max(today_open, cur)) / day_range if day_range > 0 else 0.0
    touched_high = bool(np.isfinite(previous_52_high) and today_high >= previous_52_high * .97)
    # 触及前高后收盘距当日高点超3%，并且上影线占全日振幅>=35%。
    # 只用收盘距历史高点检查，可能漏掉盘中冲高回落。
    rejection = bool(touched_high and today_high > 0 and cur / today_high <= .97 and upper_ratio >= .35)
    near_high = bool(np.isfinite(from_high) and from_high >= -3.0)

    causes = []
    if ret20 >= 25: causes.append('近20日涨幅>=25%')
    if ret60 >= 40: causes.append('近60日涨幅>=40%')
    if np.isfinite(ytd) and ytd >= 60: causes.append('年初至今涨幅>=60%')
    if rejection: causes.append('触及52周高位后冲高回落')

    missing = []
    if not np.isfinite(ytd): missing.append('年初至今基准')
    if not np.isfinite(previous_52_high): missing.append('52周历史高点')
    if causes:
        grade = '高位风险观察'
    elif missing:
        grade = '数据不完整'
    elif near_high:
        grade = '接近52周高位'
    else:
        grade = '常规位置'

    def fmt(z):
        return round(float(z), 2) if np.isfinite(z) else np.nan

    return {
        '近20日涨幅%': fmt(ret20),
        '近60日涨幅%': fmt(ret60),
        '年初至今涨幅%': fmt(ytd),
        '52周历史最高价(不含当日)': fmt(previous_52_high),
        '收盘距52周历史高点%': fmt(from_high),
        '上影线占当日振幅%': fmt(upper_ratio * 100),
        '盘中触及52周高位': touched_high,
        '高位冲高回落': rejection,
        '价格位置分类': grade,
        '价格位置风险原因': '；'.join(causes),
        '位置数据缺口': '；'.join(missing),
    }
