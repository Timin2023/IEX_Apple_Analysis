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
from flask import Flask, render_template_string, request, redirect, url_for
import matplotlib
import json


# non-interactive backend that does not require a GUI, and helps run
# flask applications better
matplotlib.use('Agg')

app = Flask(__name__)

# set environment variables and base url

base_url = 'https://cloud.iexapis.com/v1'
sandbox_url = 'https://sandbox.iexapis.com'

# request quotes and historical data

token = os.environ.get('IEX_TOKEN')
params = {'token': token}


#get_stock function allows user to enter the stock symbol they want

@app.route('/', methods=['GET', 'POST'])
def get_stock():
    if request.method == 'POST':
        symbol = request.form.get('symbol').lower()
        return redirect(url_for('stock_analysis', symbol=symbol))
    return '''
        <form method="POST">
            <label for="symbol">Enter Stock Symbol:</label><br>
            <input type="text" id="symbol" name="symbol" required><br>
            <input type="submit" value="Submit">
        </form>
        '''


@app.route('/<symbol>')
def stock_analysis(symbol):

    resp = requests.get(base_url + '/status')

    quote_url = f"{base_url}/stock/{symbol}/quote"
    historical_url = f"{base_url}/stock/{symbol}/chart/1y"

    prices = []
    timestamps = []
    historical_prices = []
    historical_timestamps = []
    volumes = []

    historical_resp = requests.get(historical_url, params=params)
    historical_resp.raise_for_status()

    historical_data = historical_resp.json()

  # Create DataFrame from the historical data for price and volume

    for data_point in historical_data: 
        historical_prices.append(data_point['close'])
        volumes.append(data_point['volume'])
        timestamp = parse(data_point['date'])
        historical_timestamps.append(timestamp)

    historical_df = pd.DataFrame({
        'Price': historical_prices,
        'Volume': volumes
    }, index=historical_timestamps)

    window_size = 20  
    no_of_std = 1  

  #calculate rolling averages for price and volume
    historical_df['RollingMeanPrice'] = historical_df['Price'].rolling(window_size).mean()
    historical_df['RollingStdPrice'] = historical_df['Price'].rolling(window_size).std()
    historical_df['BollingerHigh'] = historical_df['RollingMeanPrice'] + (historical_df['RollingStdPrice'] * no_of_std)
    historical_df['BollingerLow'] = historical_df['RollingMeanPrice'] - (historical_df['RollingStdPrice'] * no_of_std)
    historical_df['RollingMeanVolume'] = historical_df['Volume'].rolling(window_size).mean()


    #volume close algo
    def Volume_close_algo(df):
        df['Position'] = 0
        df.loc[(df['Volume'] > df['RollingMeanVolume']) & (df['Price'] > df['Price'].shift(1)), 'Position'] = 1
        df.loc[(df['Volume'] > df['RollingMeanVolume']) & (df['Price'] < df['Price'].shift(1)), 'Position'] = -1
        return df

    historical_df = Volume_close_algo(historical_df)


    #collect required data
    live_resp = requests.get(quote_url,params=params)
    live_resp.raise_for_status()
    quote_data = live_resp.json()

    df = pd.DataFrame([quote_data])
    last_traded_price = df['latestPrice']
    timestamp = datetime.datetime.now()

    prices.append(last_traded_price)
    timestamps.append(timestamp)

    #plot the last traded price
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(timestamps, prices, marker='o', markersize=5, color='red', label='Live Data')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Price')
    ax1.set_title(f'Last Traded Price for {symbol.upper()}')

    # plot the green y axis quote 
    if len(prices) > 0:
        ax1.text(timestamps[-1], prices[-1].iloc[0], f'Price: {prices[-1].iloc[0]}', color='green')
    buffer1 = io.BytesIO()
    fig1.savefig(buffer1, format='png')
    plt.close(fig1)  

    #plot the historical data as well as the bollinger bands
    fig2, (ax2, ax3) = plt.subplots(2, 1, figsize=(8, 10), sharex=True)
    ax2.plot(historical_df.index, historical_df['Price'], color='blue', label='Price')
    ax2.plot(historical_df.index, historical_df['RollingMeanPrice'], color='black', label='Rolling Mean')
    ax2.plot(historical_df.index, historical_df['BollingerHigh'], color='red', label='Bollinger High')
    ax2.plot(historical_df.index, historical_df['BollingerLow'], color='green', label='Bollinger Low')
    ax2.fill_between(historical_df.index, historical_df['BollingerHigh'], historical_df['BollingerLow'], color='gray', alpha=0.3)
    ax2.set_ylabel('Price')
    ax2.set_title(f'Historical Prices and Bollinger Bands for {symbol.upper()}')
    ax2.legend()

    #plots the volume algo positions
    ax3.plot(historical_df.index, historical_df['Position'], color='purple', label='Position')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Position (Long=1, Short=-1, Flat=0)')
    ax3.set_title('Trading Positions based on Volume and Close Price')
    ax3.legend()

    buffer2 = io.BytesIO()
    fig2.savefig(buffer2, format='png')
    plt.close(fig2)  

    buffer1.seek(0)
    buffer2.seek(0)
    image_base64_1 = base64.b64encode(buffer1.getvalue()).decode('utf-8')
    image_base64_2 = base64.b64encode(buffer2.getvalue()).decode('utf-8')

    # web page html
    html = """
      <!DOCTYPE html>
      <html>
        <head>
          <title>Stock Analysis for {symbol}</title>
          <script>
          setTimeout(function(){{
            window.location.reload(1);
          }}, 10000); 
          </script>
        </head>
        <body>
          <h1>Stock Prices for {symbol}</h1>
          <div>
            <form method="POST" action="/">
              <label for="symbol">Enter Another Stock Symbol:</label><br>
              <input type="text" id="symbol" name="symbol" required><br>
              <input type="submit" value="Submit">
            </form>
          </div>
          
          <div>
            <h2>Historical Prices and Trading Positions</h2>
            <img src="data:image/png;base64,{image_base64_2}" alt="Historical Prices and Trading Positions">
          </div>
          <div>
            <h2>Last Traded Price</h2>
            <img src="data:image/png;base64,{image_base64_1}" alt="Last Traded Price">
          </div>
        </body>
      </html>
      """.format(symbol=symbol.upper(), image_base64_1=image_base64_1, image_base64_2=image_base64_2)

    return render_template_string(html)

if __name__ == '__main__':
     app.run(debug=False,port=5000)
