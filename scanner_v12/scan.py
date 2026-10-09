"""GitHub Actions/本地运行: python scan.py --date 2026-10-09 --limit 0

仅输出技术预警及公告复核任务，不自动给出“可买”结论。
"""
import argparse
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from indicators import calc

FIELDS = 'date,code,open,high,low,close,volume,amount,tradestatus,isST'
BASE = Path(__file__).resolve().parent


def rows(res):
    if res.error_code != '0':
        raise RuntimeError(f'BaoStock: {res.error_code} {res.error_msg}')
    data=[]
    while res.next(): data.append(res.get_row_data())
    return pd.DataFrame(data,columns=res.fields)


def valid_code(code):
    # 沪深A股：非科创板。包含创业板；排除指数/ETF/北交所/688和689。
    return bool(re.fullmatch(r'(sh\.6(?!88|89)\d{5}|sz\.[03]\d{5})',code)) and not code.startswith('sz.399')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--date',default=datetime.now().strftime('%Y-%m-%d'),help='最新交易日 YYYY-MM-DD')
    ap.add_argument('--limit',type=int,default=100,help='0=全市场；先运行100只验证数据源')
    ap.add_argument('--pause',type=float,default=0.04,help='每只股票下载后休息秒数')
    ap.add_argument('--output',default='output')
    a=ap.parse_args()
    import baostock as bs
    out=BASE/a.output;out.mkdir(parents=True,exist_ok=True)
    try:
        asof = datetime.strptime(a.date, '%Y-%m-%d')
    except ValueError as exc:
        raise SystemExit('日期必须是 YYYY-MM-DD，例如 2026-10-09') from exc
    if a.limit < 0:
        raise SystemExit('--limit 必须 >= 0，0 表示全市场')
    start=(asof-timedelta(days=420)).strftime('%Y-%m-%d')
    login=bs.login()
    if login.error_code!='0': raise RuntimeError(f'登录行情源失败：{login.error_msg}')
    try:
        stocks=rows(bs.query_all_stock(day=a.date))
        if stocks.empty:
            raise RuntimeError(f'{a.date} 无股票清单（可能非交易日或数据源暂未更新）')
        stocks=stocks[stocks['code'].apply(valid_code)&stocks['tradeStatus'].eq('1')]
        stocks=stocks[~stocks['code_name'].str.contains(r'(^\*?ST|退)',case=False,regex=True,na=False)]
        stocks=stocks.sort_values('code')
        market_universe = len(stocks)
        if a.limit>0: stocks=stocks.head(a.limit)
        valid=[]; errors=[]
        for ix,r in enumerate(stocks.itertuples(index=False),1):
            code, name = r.code, r.code_name
            try:
                hist=rows(bs.query_history_k_data_plus(code,FIELDS,start_date=start,end_date=a.date,frequency='d',adjustflag='2'))
                if hist.empty: raise ValueError('无行情记录')
                # 不删除历史曾经ST的交易日，否则会扭曲20日/120日指标窗口。
                # 只排除当前股票清单中的ST标的。停牌日无交易，不参与日线指标。
                hist=hist[hist['tradestatus']=='1'].copy()
                signals=calc(hist)
                if signals['收盘日期']!=a.date: raise ValueError('数据尚未更新至目标交易日')
                valid.append({'代码':code.split('.')[1],'股票':name,**signals})
            except Exception as e:
                errors.append({'代码':code,'股票':name,'错误':str(e)})
            if ix%100==0: print(f'已处理 {ix}/{len(stocks)}, 可计算 {len(valid)}, 错误 {len(errors)}',flush=True)
            if a.pause: time.sleep(a.pause)
        if not valid: raise RuntimeError('没有成功计算的股票，请检查数据源、日期和连接')
        frame=pd.DataFrame(valid).sort_values(['已核算项通过数','预警池','五日涨幅%'],ascending=[False,False,True])
        # 未检查监管公告者定增状态一律为“未核实”，不能写成“无定增”。
        review=BASE/'placement_review.csv'
        if review.exists():
            flags=pd.read_csv(review,dtype={'代码':str},encoding='utf-8-sig')
            if not flags.empty and {'代码','状态','核验日期','公告来源'}.issubset(flags.columns):
                frame=frame.merge(flags,on='代码',how='left')
        if '状态' not in frame: frame['状态']=''
        if '核验日期' not in frame: frame['核验日期']=''
        if '公告来源' not in frame: frame['公告来源']=''
        frame['状态']=frame['状态'].fillna('').replace('', '待核实')
        frame['公告合格']=False
        for i,r in frame.iterrows():
            if r['状态']!='通过': continue
            try:
                verified_date=datetime.strptime(str(r['核验日期']),'%Y-%m-%d').date()
                frame.at[i,'公告合格']=0 <= (datetime.strptime(a.date,'%Y-%m-%d').date()-verified_date).days <= 7 and bool(str(r['公告来源']).strip())
            except (ValueError,TypeError): pass
        # 只要没有完整VPVR和当日/最新定增公告复核，都不能声称12/12或正式推荐
        frame['可直接买入']=False
        frame.to_csv(out/'全部技术结果.csv',index=False,encoding='utf-8-sig')
        frame[frame['预警池']].to_csv(out/'提前预警池.csv',index=False,encoding='utf-8-sig')
        frame[frame['已核算项通过数']>=8].to_csv(out/'强势候选待核验.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(errors,columns=['代码','股票','错误']).to_csv(out/'数据缺口.csv',index=False,encoding='utf-8-sig')
        candidate = frame[(frame['预警池']) | (frame['已核算项通过数']>=8)].copy()
        candidate[['代码','股票','状态','核验日期','公告来源']].to_csv(out/'需核查定增清单.csv',index=False,encoding='utf-8-sig')
        with open(out/'结果说明.txt','w',encoding='utf-8') as f:
            f.write(f'扫描日期：{a.date}\n当前非科创、非ST可交易股票池：{market_universe}；本次尝试：{len(stocks)}；成功计算：{len(valid)}；数据失败：{len(errors)}\n')
            if a.limit>0:
                f.write('注意：本次为有限样本测试，并非全A股扫描。\n')
            f.write(f'预警池：{int(frame["预警池"].sum())}；技术8/10以上：{int((frame["已核算项通过数"]>=8).sum())}\n')
            f.write('重要：仅有10项日线可计算；VPVR两项未核实，不能形成12/12结论。\n')
            f.write('定增仅按人工核查记录显示；待核实或记录过期均不可作为正式推荐。\n')
            f.write('ST、新股、数据缺口/停牌等可能造成样本不完整；不构成买卖建议。\n')
        print('完成：',out.resolve(),f'; 技术8/10以上：{(frame["已核算项通过数"]>=8).sum()}',flush=True)
    finally:
        bs.logout()


if __name__=='__main__': main()
