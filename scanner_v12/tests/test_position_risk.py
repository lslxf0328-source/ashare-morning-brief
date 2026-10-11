import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
import pandas as pd
from position_risk import assess_position


def series(n=290, base=10.0):
    dates = pd.bdate_range('2025-01-02', periods=n)
    return pd.DataFrame({'date': dates.strftime('%Y-%m-%d'),
                         'open': [base]*n, 'high': [base*1.01]*n,
                         'low': [base*.99]*n, 'close': [base]*n})


class PositionRiskTest(unittest.TestCase):
    def test_ytd_overheated(self):
        df = series()
        df.loc[265:, ['open', 'high', 'low', 'close']] = [17.0, 17.2, 16.8, 17.0]
        r = assess_position(df)
        self.assertEqual(r['价格位置分类'], '高位风险观察')
        self.assertGreater(r['年初至今涨幅%'], 60)

    def test_only_near_52_week_high_is_not_overheated(self):
        df = series()
        df.loc[287, 'high'] = 10.3
        df.loc[289, 'close'] = 10.2
        df.loc[289, 'high'] = 10.25
        df.loc[289, 'open'] = 10.15
        r = assess_position(df)
        self.assertEqual(r['价格位置分类'], '接近52周高位')
        self.assertFalse(r['高位冲高回落'])

    def test_intraday_high_then_rejection_detected(self):
        df = series()
        df.loc[288, 'high'] = 12.0
        df.loc[289, ['open', 'high', 'low', 'close']] = [11.4, 12.05, 11.2, 11.5]
        r = assess_position(df)
        self.assertTrue(r['高位冲高回落'])
        self.assertEqual(r['价格位置分类'], '高位风险观察')

    def test_insufficient_year_or_52wk_is_unknown(self):
        df = series(180)
        r = assess_position(df)
        self.assertEqual(r['价格位置分类'], '数据不完整')
        self.assertIn('52周历史高点', r['位置数据缺口'])

if __name__ == '__main__':
    unittest.main()
