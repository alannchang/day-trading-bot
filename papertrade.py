import requests
from datetime import datetime, timedelta
from pprint import pprint
import numpy as np
from pandas import pandas as pd
import winsound
from config import C_KEY, REFRESH

# ENDPOINTS
OC_ENDPOINT = "https://api.tdameritrade.com/v1/marketdata/chains"

class PaperT:

    def __init__(self):
        self.header = ""
        self.refresh_now = datetime.now()
        self.timestamp = ""
        self.open_trades = []

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

# TRADE MANAGEMENT

    def fetch_api_json(self, ticker, strike, contract_type, expiry):
        # GET JSON
        option_data = {
            "apikey": C_KEY,
            "symbol": ticker,
            "contractType": contract_type,
            "includeQuotes": "TRUE",
            "strategy": "SINGLE",
            "strike": strike,
            "toDate": expiry,
            "optionType": "S"}
        response = requests.get(url=OC_ENDPOINT, headers=self.header, params=option_data)
        full_data = response.json()
        # SHORTEN JSON RESPONSE
        if contract_type == "CALL":
            data = full_data['callExpDateMap']
        elif contract_type == "PUT":
            data = full_data['putExpDateMap']
        else:
            return
        # RETURN JSON
        return data

    # Basic function that uses clues from description to find a match with current open trades
    def check_match_trade(self, desc):
        # Iterate through list of open trades started from the last one
        for trade in self.open_trades[::-1]:
            # Change SPX.X to SPX, otherwise, set variable as open trade ticker
            if trade[1] == "$SPX.X":
                open_ticker = "$SPX"
            else:
                open_ticker = trade[1]
            # Return first trade with matching ticker
            if open_ticker in desc:
                return trade
        # if fails to find any match, screw it and use the most recent trade
        return self.open_trades[-1]

    def alert_trace(self, title, desc):

        if title == "ENTRY":

            # ignore all lotto plays
            if "lotto" in desc.lower():
                print(f"{datetime.now()} | ********** IGNORING LOTTO **********")
                return

            # extract ticker
            ticker = desc.split()[0]
            if ticker == "$SPX":
                ticker = "$SPX.X"

            # extract strike price
            strike = desc.split()[1][:-1]

            # extract contract type
            if desc.split()[1][-1] == "c":
                contract_type = "CALL"
            elif desc.split()[1][-1] == "p":
                contract_type = "PUT"
            else:
                return

            # set expiry to today (0DTE)
            expiry = str(datetime.now()).split()[0]

            #  GET JSON!
            data = self.fetch_api_json(ticker, strike, contract_type, expiry)

            # extract symbol from json response
            option_data = (data.popitem()[1]).popitem()[1][0]
            symbol = option_data['symbol']

            # IF NEW TRADE (NOT ALREADY PRESENT IN OPEN TRADES)
            if symbol not in self.open_trades:
                # add new trade to list and print data
                print(f"{datetime.now()} | ENTERING: {[symbol, ticker, strike, contract_type, expiry]}")
                pprint(option_data)
                # NON-TIME SENSITIVE STUFF STARTS HERE
                # update open trades list
                self.open_trades.append([symbol, ticker, strike, contract_type, expiry, option_data['mark']])
                pprint(f"OPEN TRADES: {self.open_trades}")
                winsound.PlaySound('sound/entry.wav', winsound.SND_FILENAME)

                self.record_entry(self.timestamp, title, ticker, strike, contract_type, option_data["bid"],
                                  option_data["ask"], option_data["bidAskSize"], option_data["last"],
                                  option_data["totalVolume"], option_data["openInterest"], np.nan)

        elif title == "SCALE" and len(self.open_trades) != 0:

            active_trade = self.check_match_trade(desc)

            ticker = active_trade[1]
            strike = active_trade[2]
            contract_type = active_trade[3]
            expiry = active_trade[4]

            data = self.fetch_api_json(ticker, strike, contract_type, expiry)

            option_data = (data.popitem()[1]).popitem()[1][0]

            # update open trades list
            self.open_trades.remove(active_trade)
            active_trade.append(option_data['mark'])

            print(f"{datetime.now()} | SCALING: {active_trade}")
            pprint(option_data)
            # NON-TIME SENSITIVE STUFF STARTS HERE
            # update open trades list
            self.open_trades.append(active_trade)
            pprint(f"OPEN TRADES: {self.open_trades}")

            net = round(float(active_trade[-1]) - float(active_trade[5]), 2)
            if net > 0:
                winsound.PlaySound('sound/profit.wav', winsound.SND_FILENAME)

            self.record_entry(self.timestamp, title, ticker, strike, contract_type, option_data["bid"],
                              option_data["ask"], option_data["bidAskSize"], option_data["last"],
                              option_data["totalVolume"], option_data["openInterest"], net)

        elif title == "EXIT" and len(self.open_trades) != 0:

            active_trade = self.check_match_trade(desc)

            ticker = active_trade[1]
            strike = active_trade[2]
            contract_type = active_trade[3]
            expiry = active_trade[4]

            data = self.fetch_api_json(ticker, strike, contract_type, expiry)

            option_data = (data.popitem()[1]).popitem()[1][0]

            active_trade.append(option_data['mark'])

            print(f"{datetime.now()} | EXITING {active_trade}")
            pprint(option_data)
            # NON-TIME SENSITIVE STUFF STARTS HERE
            # update open trades list
            self.open_trades.remove(active_trade)
            pprint(f"OPEN TRADES: {self.open_trades}")

            net = round(float(active_trade[-1]) - float(active_trade[5]), 2)
            if net < 0:
                winsound.PlaySound('sound/badexit.wav', winsound.SND_FILENAME)
            elif net > 0:
                winsound.PlaySound('sound/goodexit.wav', winsound.SND_FILENAME)

            self.record_entry(self.timestamp, title, ticker, strike, contract_type, option_data["bid"],
                              option_data["ask"], option_data["bidAskSize"], option_data["last"],
                              option_data["totalVolume"], option_data["openInterest"], net)

        else:
            winsound.PlaySound('sound/notify.wav', winsound.SND_FILENAME)

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
