import unittest
from IEX_apple import Volume_close_algo
from IEX_apple import app
from flask import Flask, url_for
import pandas as pd


class MyTest(unittest.TestCase):

    def setUp(self):

        self.app = app.test_client()
        self.app.testing = True
    
    def test_get_stock(self):

        response = self.app.post('/', data=dict(symbol='aapl'), follow_redirects=True)
        #if 200 returns, then it means the data from iex is clean, so that
        #is a good test to see if the system is runnning properly
        self.assertEqual(response.status_code, 200)

    def test_volume_close_algo(self):

        df = pd.DataFrame({
        'volume': [100, 200, 300, 400, 500],
        'close': [105, 180, 188, 198, 340],
        'RollingMeanVolume': [200, 200, 200, 200, 200]})

        result = Volume_close_algo(df)

        expected_positions = [0, 0, 1, 1, 1]
        #turn it into a list and compared it to the expected positions array to make sure the function is
        self.assertListEqual(result['Position'].tolist(), expected_positions)

    def test_home_data(self):
        response = self.app.get('/')
        #simple check to see if the response includes the sentance
        self.assertIn(b"Enter Stock Symbol:", response.data)

if __name__ == '__main__':
    unittest.main()
