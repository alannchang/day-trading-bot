import requests
from datetime import datetime, timedelta
import winsound
import xmltodict
import asyncio
import aiohttp
import traceback
from pprint import pprint
import dateutil.parser
from pandas import pandas as pd
from stream import TdStreamerClient
from config import C_KEY, ACCT_NUM, REFRESH

# API ENDPOINTS
UP_ENDPT = "https://api.tdameritrade.com/v1/userprincipals"
OC_ENDPOINT = "https://api.tdameritrade.com/v1/marketdata/chains"
PO_ENDPOINT = f"https://api.tdameritrade.com/v1/accounts/{ACCT_NUM}/orders"

# TRADE PARAMETERS
SIZE = 2  # Number of contracts
STOP_PRICE = .70  # SL at -25%
SCALE = [1.10, 1.20, 1.60, 2.00, 2.50, 3.00]  # +15%, +30%, +60%, +100%, +150%, 200%


class LiveT:

    def __init__(self):
        self.header = ""
        self.refresh_now = datetime.now()
        self.timestamp = ""
        self.key_list = []
        self.template = {'Symbol': '',
                         'Limit': {'Buy': set(), 'Sell': set()},
                         'Stop': {'Sell': set()}}
        self.endpoint_list = []
        self.json_list = []

# TOKEN MANAGEMENT

    def get_access(self):
        access_params = {
            "grant_type": "refresh_token",
            "refresh_token": REFRESH,
            "client_id": C_KEY
        }
        access_response = requests.post(url="https://api.tdameritrade.com/v1/oauth2/token", data=access_params)
        access_data = access_response.json()
        access_chicken = access_data['access_token']
        self.header = {"Authorization": f"Bearer {access_chicken}"}

    def refresh_access(self):
        if datetime.now() >= self.refresh_now + timedelta(minutes=29):
            self.get_access()
            self.refresh_now = datetime.now()

# STREAMING DATA MANAGEMENT

    def process_stream(self, data):
        try:
            activity = data['2']
            # exclude 'SUBSCRIBED, TransactionTrade, OrderRoute'
            if activity not in ['SUBSCRIBED', 'TransactionTrade', 'OrderRoute']:
                # convert xml to dict and store what we need in variable
                parsed_data = xmltodict.parse(data['3'])[f'{activity}Message']
                # timestamp = data['ActivityTimestamp']
                orderkey = parsed_data['Order']['OrderKey']
                ordertype = parsed_data['Order']['OrderType']
                openclose = parsed_data['Order']['OpenClose']
                orderinstruct = parsed_data['Order']['OrderInstructions']
                symbol = parsed_data['Order']['Security']['Symbol']
                if ordertype != "Market":
                    price = parsed_data['Order']['OrderPricing'][f'{ordertype}']
                else:
                    price = "MARKET"
                # if "Order" in the title, crop "Order" to be concise
                if "Order" in activity:
                    activity = activity[5:]
                # print a beautiful one line summary
                print(f"{datetime.now()}: {activity} {ordertype} {orderinstruct} to {openclose} {symbol} @ {price} ({orderkey})")
                # store order keys in most recent set of keys and print
                if len(self.key_list) > 0:
                    self.process_key(activity, ordertype, orderinstruct, orderkey, price, symbol)
                pprint(self.key_list)
        # if for whatever reason we run into an error, print all the data out
        except:
            traceback.print_exc()
            print("************ ERROR ENCOUNTERED WHILE PROCESSING STREAM, PRINTING FULL RESPONSE ************")
            pprint(data)

    def process_key(self, activity, ordertype, orderinstruct, orderkey, price, symbol):
        if activity == "EntryRequest":  # add key when order entered
            self.key_list[-1][ordertype][orderinstruct].add(orderkey)
        if activity in ["Fill", "CancelRequest"]:  # process fills or canceled orders
            # If Limit Buy filled, "Go-go-go!"
            if activity == "Fill" and ordertype == "Limit" and orderinstruct == "Buy":
                winsound.PlaySound('sound/bought.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
            # If Limit Sell filled, "CHA-CHING!" $$$
            if activity == "Fill" and ordertype == "Limit" and orderinstruct == "Sell":
                winsound.PlaySound('sound/profit.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
            # Remove order key from key list if not market order
            if price != "MARKET":
                self.key_list[-1][ordertype][orderinstruct].discard(orderkey)

        # If Stop Order canceled and number of keys in Limit Sell set equal to SIZE - 1
        if activity == "UROUT" and ordertype == "Stop" and orderinstruct == "Sell" and SIZE == len(self.key_list[-1]['Limit']['Sell']) + 1:
            new_stop_price = str(round((float(price) * 1.35), 1)) + "0"
            # iterate thru a copy of the Stop Sell keys to avoid 'runtime error: set changed size during iteration'
            for key in self.key_list[-1]['Stop']['Sell'].copy():
                self.replace_order(key, new_stop_price, symbol)
                # Remove order key from key list
                self.key_list[-1]['Stop']['Sell'].discard(key)

        # remove orderkey if UROUT and key is still in key list
        if activity == "UROUT" and orderkey in self.key_list[-1][ordertype][orderinstruct]:
            self.key_list[-1][ordertype][orderinstruct].discard(orderkey)

        # check for and remove empty key lists
        for dict in self.key_list:
            if not dict['Limit']['Buy'] and not dict['Limit']['Sell'] and not dict['Stop']['Sell']:
                self.key_list.remove(dict)
                print("************ REMOVING EMPTY KEY DICT ************")

# ORDER MANAGEMENT

    async def make_request(self, session, url, headers, json_data):
        async with session.post(url, headers=headers, json=json_data) as response:
            return response.status

    async def send_requests(self, urls, headers, json_data_list):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url, json_data in zip(urls, json_data_list):
                tasks.append(asyncio.ensure_future(self.make_request(session, url, headers, json_data)))
            responses = await asyncio.gather(*tasks)
            return responses

    async def enter_position(self, symbol, entryprice):
        # Set variables for SL, reformat entry price to string
        stop_price = str(round((entryprice * STOP_PRICE), 2))
        entry_price = str("%.2f" % entryprice)
        # SIZE constant determines number of cons, iterates for each one
        for i in range(SIZE):
            # Using SCALE constant list, each request has a unique limit sell price
            scale_price = str(round((entryprice * SCALE[i]), 2))
            # BRACKET ORDER
            order_json = {
                "orderType": "LIMIT",
                "session": "NORMAL",
                "price": entry_price,
                "duration": "DAY",
                "orderStrategyType": "TRIGGER",
                "orderLegCollection": [
                    {
                        "quantity": 1,
                        "instruction": "BUY_TO_OPEN",
                        "instrument": {
                            "assetType": "OPTION",
                            "symbol": symbol
                        }
                    }
                ],
                "childOrderStrategies": [
                    {
                        "orderStrategyType": "OCO",
                        "childOrderStrategies": [
                            {
                                "orderStrategyType": "SINGLE",
                                "session": "NORMAL",
                                "duration": "DAY",
                                "orderType": "LIMIT",
                                "price": scale_price,
                                "orderLegCollection": [
                                    {
                                        "instruction": "SELL_TO_CLOSE",
                                        "instrument": {
                                            "assetType": "OPTION",
                                            "symbol": symbol
                                        },
                                        "quantity": 1,
                                    }
                                ]
                            },
                            {
                                "orderStrategyType": "SINGLE",
                                "session": "NORMAL",
                                "duration": "DAY",
                                "orderType": "STOP",
                                "stopPrice": stop_price,
                                "orderLegCollection": [
                                    {
                                        "instruction": "SELL_TO_CLOSE",
                                        "instrument": {
                                            "assetType": "OPTION",
                                            "symbol": symbol
                                        },
                                        "quantity": 1,
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            self.json_list.append(order_json)
            self.endpoint_list.append(PO_ENDPOINT)
        # After adding jsons and endpoints, send the requests asynchronously
        status_list = await self.send_requests(self.endpoint_list, self.header, self.json_list)
        for status_code in status_list:
            if status_code == 201:
                print(f"{datetime.now()} | ENTRY ORDER PLACED!")
                winsound.PlaySound('sound/entry.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                print(f"{datetime.now()} | ENTRY ORDER FAILED TO PLACE!")
                winsound.PlaySound('sound/codec.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
        # create a new set of keys
        self.key_list.append(self.template)
        # add symbol for future reference
        self.key_list[-1]['Symbol'] = symbol
        # clear lists for asyncio, aiohttp
        self.json_list, self.endpoint_list = [], []

    # replace orders to raise stop losses to ~BE
    def replace_order(self, orderkey, stop_price, symbol):
        order_json = {
                        "orderStrategyType": "SINGLE",
                        "session": "NORMAL",
                        "duration": "DAY",
                        "orderType": "STOP",
                        "stopPrice": stop_price,
                        "orderLegCollection": [
                            {
                                "instruction": "SELL_TO_CLOSE",
                                "instrument": {
                                    "assetType": "OPTION",
                                    "symbol": symbol
                                },
                                "quantity": 1,
                            }
                        ]
                    }

        order_response = requests.put(url=f"{PO_ENDPOINT}/{orderkey}", headers=self.header, json=order_json)
        if 200 <= order_response.status_code < 300:
            print(f"{datetime.now()} | ********** MOVING SL TO {stop_price} **********")
            winsound.PlaySound('sound/stoplossup.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            print(f"{datetime.now()} | ********** {order_response.status_code}: FAILED TO REPLACE ORDER {orderkey} **********")
            winsound.PlaySound('sound/codec.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)

    # replace stop orders to market sells to quickly exit position
    def replace_order_market(self, orderkey, symbol):
        order_json = {
                        "orderStrategyType": "SINGLE",
                        "session": "NORMAL",
                        "duration": "DAY",
                        "orderType": "MARKET",
                        "orderLegCollection": [
                            {
                                "instruction": "SELL_TO_CLOSE",
                                "instrument": {
                                    "assetType": "OPTION",
                                    "symbol": symbol
                                },
                                "quantity": 1,
                            }
                        ]
                    }

        order_response = requests.put(url=f"{PO_ENDPOINT}/{orderkey}", headers=self.header, json=order_json)
        if 200 <= order_response.status_code < 300:
            print(f"{datetime.now()} | ********** REPLACING SL ORDER {orderkey} WITH MARKET SELL ORDER **********")
            winsound.PlaySound('sound/stoplossup.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            print(f"{datetime.now()} | ********** {order_response.status_code}: FAILED TO REPLACE ORDER {orderkey} **********")
            winsound.PlaySound('sound/codec.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)

    def cancel_order(self, orderkey):
        order_response = requests.delete(url=f"{PO_ENDPOINT}/{orderkey}", headers=self.header)
        if 200 <= order_response.status_code < 300:
            print(f"{datetime.now()} | ********** SUCCESSFULLY CANCELED ORDER {orderkey} **********")
            winsound.PlaySound('sound/dodged.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            print(f"{datetime.now()} | ********** {order_response.status_code}: FAILED TO CANCEL ORDER {orderkey} **********")
            winsound.PlaySound('sound/codec.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)

    async def alert_trace(self, title, desc):

        if "entering" in title.lower():

            # ignore all lotto/risky/swing plays
            if "risky" in desc.lower() or "swing" in desc.lower() or "lotto" in desc.lower():
                print(f"{datetime.now()} | ********** IGNORING RISKY/SWING/LOTTO PLAY **********")
                return

            arr = desc.split()

            # extract ticker
            for i in range(len(arr)):
                if arr[i] == "Option:":
                    ticker = arr[i + 1]
                    strike = arr[i + 2]
                    contract_type = arr[i + 3]
                    expiry = arr[i + 4]

                if arr[i] == "Entry:":
                    if arr[i + 1][0] == "@" and arr[i + 1][1] == "$":
                        entry_price = float(arr[i + 1][2:])
                    else:
                        entry_price = float(arr[i + 1])

            if ticker == "SPX":
                ticker = "SPXW"

            # set expiry to today (0DTE)
            current_year = datetime.now().year
            date_parts = expiry.split('/')
            month = int(date_parts[0])
            day = int(date_parts[1])

            expiry = "{:02d}{:02d}{:02d}".format(month, day, current_year % 100)

            # combine variables to create symbol
            symbol = f"{ticker}_{expiry}{contract_type}{strike}"
            # send post orders asynchronously
            await self.enter_position(symbol, entry_price)

        elif title == "EXIT":

            # if EXIT alerted but no buys filled yet
            if self.key_list and len(self.key_list[-1]['Limit']['Sell']) == 0 and len(self.key_list[-1]['Stop']['Sell']) == 0 and len(self.key_list[-1]['Limit']['Buy']) > 0:
                for key in self.key_list[-1]['Limit']['Buy']:
                    self.cancel_order(key)
            # if EXIT alerted after all buys filled
            if self.key_list and len(self.key_list[-1]['Limit']['Buy']) == 0 and len(self.key_list[-1]['Stop']['Sell']) > 0 and len(self.key_list[-1]['Limit']['Sell']) > 0:
                # replace all stop sells with market sells
                for key in self.key_list[-1]['Stop']['Sell']:
                    symbol = self.key_list[-1]['Symbol']
                    self.replace_order_market(key, symbol)
            # Remove template after exiting
            # if self.key_list:
            #     # slice last element off list
            #     self.key_list = self.key_list[:-1]

# STREAMING DATA

    def get_user_principals(self, fields):
        body = {"fields": fields}
        response = requests.get(url=UP_ENDPT, headers=self.header, params=body)
        return response.json()

    def create_token_timestamp(self, token_timestamp=None):
        # First, parse the timestamp
        token_timestamp = dateutil.parser.parse(token_timestamp, ignoretz=True)
        # Grab the starting point
        epoch = datetime.utcfromtimestamp(0)
        return int((token_timestamp - epoch).total_seconds() * 1000)

    def create_streaming_session(self):
        # grab streamer info
        principals_response = self.get_user_principals("streamerConnectionInfo,streamerSubscriptionKeys")
        # grab timestamp
        t_timestamp = principals_response['streamerInfo']['tokenTimestamp']
        # grab socket
        socket_url = principals_response['streamerInfo']['streamerSocketUrl']
        # parse timestamp
        t_timestamp_ms = self.create_token_timestamp(token_timestamp=t_timestamp)
        # define credentials dictionary used for authentication
        credentials = {
            "userid": principals_response['accounts'][0]['accountId'],
            "token": principals_response['streamerInfo']['token'],
            "company": principals_response['accounts'][0]['company'],
            "segment": principals_response['accounts'][0]['segment'],
            "cddomain": principals_response['accounts'][0]['accountCdDomainId'],
            "usergroup": principals_response['streamerInfo']['userGroup'],
            "accesslevel": principals_response['streamerInfo']['accessLevel'],
            "authorized": "Y",
            "timestamp": t_timestamp_ms,
            "appid": principals_response['streamerInfo']['appId'],
            "acl": principals_response['streamerInfo']['acl']
        }

        streaming_session = TdStreamerClient(websocket_url=socket_url, principal_data=principals_response, credentials=credentials)
        return streaming_session


# RECORD/DATA MANAGEMENT

    @staticmethod
    def record_entry(time, action, ticker, strike, contracttype, bid, ask, bidasksize, last, totalvolume,
                     openinterest, net):
        new_entry = {
            'Time': [time],
            'Action': [action],
            'Ticker': [ticker],
            'Strike': [strike],
            'C/P': [contracttype],
            'bid': [bid],
            'ask': [ask],
            'bidAskSize': [bidasksize],
            'last': [last],
            'totalVolume': [totalvolume],
            'openInterest': [openinterest],
            'net': [net]
        }
        df = pd.read_csv("paperdata.csv")
        row_dd = pd.DataFrame(new_entry)
        new_dd = pd.concat([df, row_dd], ignore_index=True)
        new_dd.to_csv("paperdata.csv", index=False)
