import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
import numpy as np
import datetime
from dateutil.parser import parse
from flask import Flask, render_template_string
import matplotlib
import json

# non-interactive backend that does not require a GUI, and helps run
# flask applications better
matplotlib.use('Agg')


app = Flask(__name__)

# set environment variables and base url

base_url = 'https://cloud.iexapis.com/v1'
sandbox_url = 'https://sandbox.iexapis.com'

token = os.environ.get('IEX_TOKEN')
params = {'token': token}

# request quotes and historical data

resp = requests.get(base_url + '/status')

quote_url = f"{base_url}/stock/aapl/quote"
historical_url = f"{base_url}/stock/aapl/chart/1y"

# create 
prices = []
timestamps = []
historical_prices = []
historical_timestamps = []
volumes = []

# retrieves the historical data
historical_resp = requests.get(historical_url, params=params)
historical_resp.raise_for_status()

historical_data = historical_resp.json()

# gets the close and volume every day and appends it
# does the same with the timestamps
for data_point in historical_data: 
    historical_prices.append(data_point['close'])
    volumes.append(data_point['volume'])
    timestamp = parse(data_point['date'])
    historical_timestamps.append(timestamp)

# Create DataFrame from the historical data for price and volume
historical_df = pd.DataFrame({
    'Price': historical_prices,
    'Volume': volumes
}, index=historical_timestamps)

window_size = 20  # adjust to the appropriate window size
no_of_std = 1  # adjust to the number of standard deviations for Bollinger Bands

historical_df['RollingMeanPrice'] = historical_df['Price'].rolling(window_size).mean()
historical_df['RollingStdPrice'] = historical_df['Price'].rolling(window_size).std()
historical_df['BollingerHigh'] = historical_df['RollingMeanPrice'] + (historical_df['RollingStdPrice'] * no_of_std)
historical_df['BollingerLow'] = historical_df['RollingMeanPrice'] - (historical_df['RollingStdPrice'] * no_of_std)
historical_df['RollingMeanVolume'] = historical_df['Volume'].rolling(window_size).mean()


# Strategy algo
def Volume_close_algo(df):
    '''Function will evaluate the volume against its rolling mean and close prices'''

    df['Position'] = 0

    # If today's volume is greater than its rolling mean volume of the past days and
    # today's close price is higher than yesterday's, then go long
    df.loc[(df['Volume'] > df['RollingMeanVolume']) & (df['Price'] > df['Price'].shift(1)), 'Position'] = 1
    
    # If today's volume is greater than its rolling mean volume of the past days and
    # today's close price is lower than yesterday's, then go short
    df.loc[(df['Volume'] > df['RollingMeanVolume']) & (df['Price'] < df['Price'].shift(1)), 'Position'] = -1
    
    return df

historical_df = Volume_close_algo(historical_df)

@app.route('/')
def serve_image():
    # Retrieve the live data for plotting
    live_resp = requests.get(quote_url,params=params)
    live_resp.raise_for_status()
    quote_data = live_resp.json()

    df = pd.DataFrame([quote_data])
    last_traded_price = df['latestPrice']
    timestamp = datetime.datetime.now()

    prices.append(last_traded_price)
    timestamps.append(timestamp)

    # plot the live data for last traded price
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(timestamps, prices, marker='o', markersize=5, color='red', label='Live Data')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Price')
    ax1.set_title('Last Traded Price for AAPL')

    # print the last price on y axis
    if len(prices) > 0:
        ax1.text(timestamps[-1], prices[-1].iloc[0], f'Price: {prices[-1].iloc[0]}', color='green')
    buffer1 = io.BytesIO()
    fig1.savefig(buffer1, format='png')
    plt.close(fig1)  # Must close the figure, otherwise it will interfere with other plots

    # historical data and positions for the historical data and boillinger bands
    fig2, (ax2, ax3) = plt.subplots(2, 1, figsize=(8, 10), sharex=True)
    ax2.plot(historical_df.index, historical_df['Price'], color='blue', label='Price')
    ax2.plot(historical_df.index, historical_df['RollingMeanPrice'], color='black', label='Rolling Mean')
    ax2.plot(historical_df.index, historical_df['BollingerHigh'], color='red', label='Bollinger High')
    ax2.plot(historical_df.index, historical_df['BollingerLow'], color='green', label='Bollinger Low')
    ax2.fill_between(historical_df.index, historical_df['BollingerHigh'], historical_df['BollingerLow'], color='gray', alpha=0.3)
    ax2.set_ylabel('Price')
    ax2.set_title('Historical Prices and Bollinger Bands for AAPL')
    ax2.legend()

    ax3.plot(historical_df.index, historical_df['Position'], color='purple', label='Position')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Position (Long=1, Short=-1, Flat=0)')
    ax3.set_title('Trading Positions based on Volume and Close Price')
    ax3.legend()

    buffer2 = io.BytesIO()
    fig2.savefig(buffer2, format='png')
    plt.close(fig2)  # close the figure or otherwise it will interfere with other plots

    buffer1.seek(0)
    buffer2.seek(0)
    image_base64_1 = base64.b64encode(buffer1.getvalue()).decode('utf-8')
    image_base64_2 = base64.b64encode(buffer2.getvalue()).decode('utf-8')

    # Embed the base64 image data in the HTML response using a template string
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Stock Analysis for AAPL</title>
        <script>
        setTimeout(function(){
           window.location.reload(1);
        }, 10000); 
        </script>
      </head>
      <body>
        <h1>Stock Prices for AAPL</h1>
        <div>
          <h2>Last Traded Price</h2>
          <img src="data:image/png;base64,{{ image_base64_1 }}" alt="Last Traded Price">
        </div>
        <div>
          <h2>Historical Prices and Trading Positions</h2>
          <img src="data:image/png;base64,{{ image_base64_2 }}" alt="Historical Prices and Trading Positions">
        </div>
      </body>
    </html>
    """
    return render_template_string(html, image_base64_1=image_base64_1, image_base64_2=image_base64_2)

if __name__ == '__main__':
     app.run(debug=False,port=5000)

