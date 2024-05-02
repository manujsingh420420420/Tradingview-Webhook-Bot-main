import json
from flask import Flask, render_template, request, jsonify
from pybit import HTTP
import MetaTrader5 as mt5
import pandas as pd
import time
import ccxt
#from binanceFutures import Bot



def validate_bybit_api_key(session):
    try:
        result = session.get_api_key_info()
        return True
    except Exception as e:
        print("Bybit API key validation failed:", str(e))
        return False

def validate_binance_api_key(exchange):
    try:
        result = exchange.fetch_balance()
        return True
    except Exception as e:
        print("Binance API key validation failed:", str(e))
        return False

app = Flask(__name__)

# load config.json
with open('config.json') as config_file:
    config = json.load(config_file)

###############################################################################
#
#             This Section is for Exchange Validation
#
###############################################################################

use_bybit = False
if 'BYBIT' in config['EXCHANGES']:
    if config['EXCHANGES']['BYBIT']['ENABLED']:
        print("Bybit is enabled!")
        use_bybit = True

    session = HTTP(
        endpoint='https://api.bybit.com',
        api_key=config['EXCHANGES']['BYBIT']['API_KEY'],
        api_secret=config['EXCHANGES']['BYBIT']['API_SECRET']
    )

use_binance_futures = False
if 'BINANCE-FUTURES' in config['EXCHANGES']:
    if config['EXCHANGES']['BINANCE-FUTURES']['ENABLED']:
        print("Binance is enabled!")
        use_binance_futures = True

        exchange = ccxt.binance({
        'apiKey': config['EXCHANGES']['BINANCE-FUTURES']['API_KEY'],
        'secret': config['EXCHANGES']['BINANCE-FUTURES']['API_SECRET'],
        'options': {
            'defaultType': 'future',
            },
        'urls': {
            'api': {
                'public': 'https://testnet.binancefuture.com/fapi/v1',
                'private': 'https://testnet.binancefuture.com/fapi/v1',
            }, }
        })
        exchange.set_sandbox_mode(True)

# Validate Bybit API key
if use_bybit:
    if not validate_bybit_api_key(session):
        print("Invalid Bybit API key.")
        use_bybit = False

# Validate Binance Futures API key
if use_binance_futures:
    if not validate_binance_api_key(exchange):
        print("Invalid Binance Futures API key.")
        use_binance_futures = False

@app.route('/')
def index():
    return {'message': 'Server is running!'}

@app.route('/webhook', methods=['POST'])
def webhook():
    print("Hook Received!")
    data = json.loads(request.data)
    print(data)
    print("*"*100)

    if int(data['key']) != config['KEY']:
        print("Invalid Key, Please Try Again!")
        return {
            "status": "error",
            "message": "Invalid Key, Please Try Again!"
        }

    ##############################################################################
    #             MT5
    ##############################################################################
    mt5.initialize()
    if not mt5.initialize():
        print("initialize() failed, error code =",mt5.last_error())
        quit()
    login = 5025048005
    password = 'Vb+8NiHv'
    server ='MetaQuotes-Demo'

    mt5.login(login,password,server)
    accountinfo = mt5.account_info()
    print(accountinfo)
    print("*" * 100)
    ea_magic_number = 9986989

    symbol = data['symbol']
    percentage_sl = float(data['percentage_sl'])
    percentage_tp = float(data['percentage_tp'])
    
    deviation = 20
    price = float(data['price'])
    positions = mt5.positions_get()
    colonnes = ["ticket", "position", "symbol", "volume", "magic", "profit", "price", "tp", "sl","trade_size"]
    summary = pd.DataFrame()
    for element in positions:
                element_pandas = pd.DataFrame([element.ticket, element.type, element.symbol, element.volume, element.magic,
                                               element.profit, element.price_open, element.tp,
                                               element.sl, mt5.symbol_info(element.symbol).trade_contract_size],
                                              index=colonnes).transpose()
                summary = pd.concat((summary, element_pandas), axis=0)

    print(summary)
    print("*" * 100)
    def open_trade(action, symbol, lot,ea_magic_number):
        if action == 'buy':
            trade_type = mt5.ORDER_TYPE_BUY
            buy_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": lot,
                        "type": trade_type,
                        "price": mt5.symbol_info_tick(symbol).ask,
                        "sl" : mt5.symbol_info_tick(symbol).ask * (1 - percentage_sl/1000),
                        "tp" : mt5.symbol_info_tick(symbol).ask * (1 + percentage_tp/1000),
                        "deviation": deviation,
                        "magic": ea_magic_number,
                        "comment": "sent by python",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC, # good till cancelled
                     }
                
        elif action =='sell':
            trade_type = mt5.ORDER_TYPE_SELL
            buy_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": lot,
                        "type": trade_type,
                        "price": mt5.symbol_info_tick(symbol).bid,
                        "sl" : mt5.symbol_info_tick(symbol).bid * (1 + percentage_sl/1000),
                        "tp" : mt5.symbol_info_tick(symbol).bid * (1 - percentage_tp/1000),
                        "deviation": deviation,
                        "magic": ea_magic_number,
                        "comment": "sent by python",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC, # good till cancelled
                     }
        else:
            buy_request = None

        
            # send a trading request
        result = mt5.order_send(buy_request)        
        return result
    
    
     
    action = data['side']
    lot = float(data['qty'])

    symbol_df = pd.DataFrame()
    if summary.empty:
        print("No Orders Yet")
        print("*" * 100)
    else:
        try:
            symbol_df = summary["symbol"]
            size = symbol_df.size
        except:
            symbol_df = pd.DataFrame()
            size = symbol_df.size 


    if symbol_df.empty:
        print("No Orders Yet")
        print("*" * 100)
    else:
        try:
            for i in range(0,size):
                if symbol_df.iloc[i] == symbol:
                    identifier = summary.iloc[i][0]
            mt5.Close(symbol,ticket=identifier)        

        except:
            identifier = None
    print("POSITIONS BEFORE NEW SIGNAL")
    print(summary)
    print("*" * 100)
    
    result= open_trade(action, symbol , lot, ea_magic_number)
    
        
    positions = mt5.positions_get()
    colonnes = ["ticket", "position", "symbol", "volume", "magic", "profit", "price", "tp", "sl","trade_size"]
    summary2 = pd.DataFrame()
    for element in positions:
                element_pandas = pd.DataFrame([element.ticket, element.type, element.symbol, element.volume, element.magic,
                                               element.profit, element.price_open, element.tp,
                                               element.sl, mt5.symbol_info(element.symbol).trade_contract_size],
                                              index=colonnes).transpose()
                summary2 = pd.concat((summary2, element_pandas), axis=0)
    print("POSITIONS AFTER NEW SIGNAL")
    print(summary2)

    
    
    return {
            "status": "success",
            "message": "Bybit Webhook Received!",
            "result" : result,
            
        }

if __name__ == '__main__':
    app.run(debug=False)


