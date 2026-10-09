import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import numpy as np
import pandas as pd
from indicators import calc

class SignalsTest(unittest.TestCase):
    def test_can_calculate_and_no_lookahead(self):
        rng=np.random.default_rng(42)
        price=15+np.arange(230)*0.04 + rng.normal(0,.25,230)
        close=pd.Series(price)
        df=pd.DataFrame({'date':pd.date_range('2025-01-01',periods=230,freq='B').strftime('%Y-%m-%d'),
          'open':close-.02,'high':close+0.4,'low':close-0.4,'close':close,
          'volume':np.arange(230)*400+100000,'amount':(close*np.arange(230)*400+100000).astype(float)})
        result=calc(df)
        self.assertEqual(result['已核算项总数'],10)
        self.assertEqual(result['VPVR两项'],'未核验')
        self.assertGreater(result['收盘价'],0)
        self.assertLessEqual(result['已核算项通过数'],10)
        # 当日创新高不应纳入前20日高点
        df.loc[229,'high']=100
        result2=calc(df)
        self.assertEqual(result['突破位'],result2['突破位'])

if __name__ == '__main__': unittest.main()
