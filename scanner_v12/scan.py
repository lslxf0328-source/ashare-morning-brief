"""
GitHub Actions/本地运行:

python scan.py --date 2026-10-09 --limit 0

仅输出技术预警及公告复核任务，
不自动给出“可买”结论。
"""

import argparse
import re
import time
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

from indicators import calc
from position_risk import assess_position
from placement_risk import assess_placement_risk


FIELDS = (
    'date,code,open,high,low,close,volume,amount,'
    'tradestatus,isST'
)

BASE = Path(__file__).resolve().parent


def rows(res):

    if res.error_code != '0':
        raise RuntimeError(
            f'BaoStock: {res.error_code} {res.error_msg}'
        )

    data=[]

    while res.next():
        data.append(
            res.get_row_data()
        )

    return pd.DataFrame(
        data,
        columns=res.fields
    )



def valid_code(code):

    # 沪深A股
    # 排除科创、北交、指数ETF

    return bool(
        re.fullmatch(
            r'(sh\.6(?!88|89)\d{5}|sz\.[03]\d{5})',
            code
        )
    ) and not code.startswith('sz.399')



def main():

    ap=argparse.ArgumentParser()

    ap.add_argument(
        '--date',
        default=datetime.now().strftime('%Y-%m-%d')
    )

    ap.add_argument(
        '--limit',
        type=int,
        default=100
    )

    ap.add_argument(
        '--pause',
        type=float,
        default=0.04
    )

    ap.add_argument(
        '--output',
        default='output'
    )

    a=ap.parse_args()


    import baostock as bs


    out=BASE/a.output

    out.mkdir(
        parents=True,
        exist_ok=True
    )


    try:

        asof=datetime.strptime(
            a.date,
            '%Y-%m-%d'
        )

    except ValueError:

        raise SystemExit(
            '日期格式错误'
        )


    start=(
        asof-timedelta(days=420)
    ).strftime('%Y-%m-%d')


    login=bs.login()

    if login.error_code!='0':

        raise RuntimeError(
            login.error_msg
        )


    try:


        stocks=rows(
            bs.query_all_stock(
                day=a.date
            )
        )


        if stocks.empty:

            raise RuntimeError(
                '无股票数据'
            )


        stocks=stocks[
            stocks['code'].apply(valid_code)
            &
            stocks['tradeStatus'].eq('1')
        ]


        stocks=stocks[
            ~stocks['code_name']
            .str
            .contains(
                r'(^\*?ST|退)',
                regex=True,
                na=False
            )
        ]


        stocks=stocks.sort_values(
            'code'
        )


        market_universe=len(stocks)


        if a.limit>0:

            stocks=stocks.head(
                a.limit
            )


        valid=[]
        errors=[]


        for ix,r in enumerate(
            stocks.itertuples(index=False),
            1
        ):

            code=r.code
            name=r.code_name

            try:

                hist=rows(
                    bs.query_history_k_data_plus(
                        code,
                        FIELDS,
                        start_date=start,
                        end_date=a.date,
                        frequency='d',
                        adjustflag='2'
                    )
                )


                if hist.empty:

                    raise ValueError(
                        '无行情'
                    )


                hist=hist[
                    hist['tradestatus']=='1'
                ].copy()


                signals=calc(hist)


                if signals['收盘日期']!=a.date:

                    raise ValueError(
                        '数据未更新'
                    )


                # 原位置风险模块
                signals.update(
                    assess_position(hist)
                )


                valid.append(
                    {
                        '代码':code.split('.')[1],
                        '股票':name,
                        **signals
                    }
                )


            except Exception as e:


                errors.append(
                    {
                        '代码':code,
                        '股票':name,
                        '错误':str(e)
                    }
                )


            if ix%100==0:

                print(
                    f'已处理 {ix}/{len(stocks)}'
                )


            if a.pause:

                time.sleep(a.pause)
                        if not valid:

            raise RuntimeError(
                '没有成功计算股票'
            )


        frame=pd.DataFrame(valid)


        # ==========================
        # 原位置排序逻辑 保留
        # ==========================

        grade_order={
            '常规位置':0,
            '接近52周高位':1,
            '数据不完整':2,
            '高位风险观察':3
        }


        frame['_位置排序']=(
            frame['价格位置分类']
            .map(grade_order)
            .fillna(4)
        )


        frame=frame.sort_values(
            [
                '_位置排序',
                '已核算项通过数',
                '预警池',
                '五日涨幅%'
            ],
            ascending=[
                True,
                False,
                False,
                True
            ]
        ).drop(
            columns=['_位置排序']
        )



        # ==========================
        # 定增风险模块 V1.2
        # ==========================

        review=BASE/'placement_review.csv'


        if review.exists():

            flags=pd.read_csv(
                review,
                dtype={'代码':str},
                encoding='utf-8-sig'
            )


            if (
                not flags.empty
                and
                {
                    '代码',
                    '状态',
                    '核验日期',
                    '公告来源'
                }.issubset(flags.columns)
            ):

                frame=frame.merge(
                    flags,
                    on='代码',
                    how='left'
                )


        # 缺省字段

        for col in [
            '状态',
            '核验日期',
            '公告来源'
        ]:

            if col not in frame.columns:

                frame[col]=''



        frame['状态']=(
            frame['状态']
            .fillna('')
            .replace(
                '',
                '待核实'
            )
        )



        frame['公告合格']=False



        for i,r in frame.iterrows():

            if r['状态']!='通过':

                continue


            try:

                verified_date=datetime.strptime(
                    str(r['核验日期']),
                    '%Y-%m-%d'
                ).date()


                frame.at[i,'公告合格']=(
                    0 <=
                    (
                        datetime.strptime(
                            a.date,
                            '%Y-%m-%d'
                        ).date()
                        -
                        verified_date
                    ).days
                    <=7
                    and
                    bool(
                        str(
                            r['公告来源']
                        ).strip()
                    )
                )


            except Exception:

                pass



        # 计算定增风险

        placement_results=[]


        for _,r in frame.iterrows():

            placement_info={

                '状态':
                    r['状态'],

                '公告合格':
                    r['公告合格']

            }


            placement_results.append(

                assess_placement_risk(
                    placement_info
                )

            )



        placement_df=pd.DataFrame(
            placement_results
        )



        frame=pd.concat(
            [
                frame.reset_index(drop=True),
                placement_df.reset_index(drop=True)
            ],
            axis=1
        )



        # ==========================
        # 买入权限
        # ==========================

        frame['可直接买入']=False



        common=(
            frame['价格位置分类']
            .eq('常规位置')
        )


        strong=(
            frame['已核算项通过数']
            >=8
        )


        early=frame['预警池']



        # A级定增风险禁止

        if 'placement_risk_level' in frame.columns:

            risk_high=(
                frame['placement_risk_level']
                =='A'
            )

        else:

            risk_high=False



        frame.loc[
            (
                early
                |
                strong
            )
            &
            common
            &
            (~risk_high),
            '可直接买入'
        ]=False



        # ==========================
        # 输出
        # ==========================


        frame.to_csv(
            out/'全部技术结果.csv',
            index=False,
            encoding='utf-8-sig'
        )


        frame[
            early & common
        ].to_csv(
            out/'提前预警池.csv',
            index=False,
            encoding='utf-8-sig'
        )


        frame[
            strong & common
        ].to_csv(
            out/'强势候选待核验.csv',
            index=False,
            encoding='utf-8-sig'
        )


        frame[
            (early | strong)
            &
            (~common)
        ].to_csv(
            out/'高位及数据不全观察池.csv',
            index=False,
            encoding='utf-8-sig'
        )



        candidate=frame[
            early | strong
        ].copy()



        candidate[
            [
                '代码',
                '股票',
                '状态',
                '核验日期',
                '公告来源',
                'placement_risk_level',
                'placement_risk_score',
                'placement_risk_reason'
            ]
        ].to_csv(
            out/'需核查定增清单.csv',
            index=False,
            encoding='utf-8-sig'
        )



        pd.DataFrame(
            errors,
            columns=[
                '代码',
                '股票',
                '错误'
            ]
        ).to_csv(
            out/'数据缺口.csv',
            index=False,
            encoding='utf-8-sig'
        )



        with open(
            out/'结果说明.txt',
            'w',
            encoding='utf-8'
        ) as f:


            f.write(
                f'扫描日期：{a.date}\n'
            )

            f.write(
                f'股票池：{market_universe}\n'
            )

            f.write(
                f'成功计算：{len(valid)}\n'
            )

            f.write(
                f'技术8/10以上：{int(strong.sum())}\n'
            )

            f.write(
                f'定增A风险数量：'
                f'{int((frame["placement_risk_level"]=="A").sum())}\n'
            )

            f.write(
                '定增未核实股票不得作为正式推荐。\n'
            )



        print(
            '完成:',
            out.resolve()
        )



    finally:

        bs.logout()



if __name__=='__main__':

    main()
