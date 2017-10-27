import requests
import sys
import hashlib
import hmac
import base64
from colorama import Fore, Back, Style, init
from time import time

init()

# Params set by user
BASE_URL = "https://bittrex.com/api/v1.1/"
API_KEY = "<API-KEY-HERE>"
API_SECRET = "<API=SECRET-HERE>"
units_bought = 0
currency = sys.argv[1]
market_name = "BTC-" + currency
BOT_TYPE = int(sys.argv[2])


# Helper classes that define static properties for common api paths
class URI_public:
    markets = "public/getmarkets"
    currencies = "public/getcurrencies"
    market_ticker = "public/getticker?market=%s"
    market_day_summaries = "public/getmarketsummaries"
    market_day_summary = "public/getmarketsummary?market=%s"
    order_book = "public/getorderbook?market=%s&type=%s&depth=%s"
    last_trades = "public/getmarkethistory?market=%s"


class URI_account:
    balance = "account/getbalances"
    currency_balance = "account/getbalance?currency=%s"
    deposit_address = "account/getdepositaddress?currency=%s"
    withdraw = "account/withdraw?currency=%s&quantity=%s&address=%s"
    get_order_by_uuid = "account/getorder&uuid=%s"
    orders_history = "account/getorderhistory"
    market_orders_history = "account/getorderhistory?market=%s"
    withdrawal_history = "account/getwithdrawalhistory?currency=%s"
    deposit_history = "account/getwithdrawalhistory?currency=%s"


class URI_market:
    buy = "market/buylimit?market=%s&quantity=%s&rate=%s"
    sell = "market/selllimit?market=%s&quantity=%s&rate=%s"
    cancel_by_uuid = "market/cancel?uuid=%s"
    open_orders = "market/getopenorders?market=%s"


def hmac_sha512(url, key):
    digest = hmac.new(API_SECRET, url, hashlib.sha512).hexdigest()
    return digest

# print("This is the a property from a class dynamically: " + getattr(URI_market,'buy'))


def get_url(api_type, **params):
    """This funtion gets the REST url for a given api type + params"""
    global BASE_URL
    url = BASE_URL + getattr(api_type, params["action"])
    if params["action"] == "buy" or params["action"] == "sell":
        # sprintf(url, params[:market], params[:quantity], params[:rate])
        url = url % (params["market"], params["quantity"], params["rate"])
    elif params["action"] == "cancel_by_uuid":
        url = url % (params["uuid"])
    elif params["action"] == "open_orders" or params["action"] == "market_ticker" or params["action"] == "market_day_summary" or params["action"] == "last_trades" or params["action"] == "market_orders_history":
        url = url % (params["market"])
    elif params["action"] == "currency_balance" or params["action"] == "deposit_address":
        url = url % (params["currency"])
    elif params["action"] == "order_book":
        url = url % (params["market"], params["order_type"], params["depth"])

    nonce = time()
    # +" if ["market", "account"]params[:api_type]
    if str(api_type.__name__) =="URI_market" or str(api_type.__name__) == "URI_account":
          if "?" not in url:
              url = url + "?apikey=" + API_KEY + "&nonce=" + str(nonce)
          else:
              url = url + "&apikey=" + API_KEY + "&nonce=" + str(nonce)

    return url

def call_api(url):
    try:
        response = requests.get(url, verify=False)
        parsed_body = response.json()
        print Fore.YELLOW,"Fetching Market Summary..."
        #print (url + "\n" + parsed_body)
        print Fore.GREEN + "Success" if parsed_body["success"] is True else Fore.RED + "Failed"
        if parsed_body["success"] is True:
          return parsed_body["result"] 
    except:
      print "Call api failed: " , sys.exc_info()[0]

def call_secret_api(url):
  sign = hmac_sha512(url, API_SECRET)
  response = requests.get(url, verify=False, headers={'apisign': hmac_sha512(url, API_SECRET)})
  print Fore.YELLOW , "Calling API..."
  #print response
  parsed_body = response.json()
  #p [url, parsed_body]
  print Fore.GREEN + "Success" if parsed_body["success"] is True else Fore.RED + "Failed"
  if parsed_body["success"] is True:
      return parsed_body["result"] 

# method to cancel all open BTC pair orders on bittrex
def cancel_all_bot():
  """ method to cancel all open BTC pair orders on bittrex"""
  markets_url = get_url(URI_public, action = "markets")
  markets = call_api(markets_url)
  global currency
  for market in markets:
    currency = market["MarketCurrency"]
    base_currency = market["BaseCurrency"]
    global market_name
    market_name = market["MarketName"]
    if market["IsActive"] and base_currency == "BTC":
      open_orders_url = get_url(URI_market, action = "open_orders", market = market_name)
      open_orders = call_secret_api(open_orders_url)
      if open_orders.size > 0:
        print market_name, open_orders
        for open_order in open_orders:
          cancel_order_url = get_url(URI_market, action = "cancel_by_uuid", uuid = open_order["OrderUuid"])
          order = call_secret_api(cancel_order_url)
        print("Orders cancelled for %s") %(market_name)


# method to sell all BTC pair orders on bittrex
# params- profit_rate(float)[default = 0.2] at which sell orders need to be set
def sell_all_bot(profit_rate = 0.2):
  markets_url = get_url(URI_public, action = "markets")
  markets = call_api(markets_url)
  expected_worth = 0.0
  global currency
  for market in markets:
    currency = market["MarketCurrency"]
    base_currency = market["BaseCurrency"]
    global market_name
    market_name = market["MarketName"]
    if market["IsActive"] and base_currency == "BTC":
      get_balance_url = get_url(URI_account, action = "currency_balance", currency = currency)
      balance_details = call_secret_api(get_balance_url)
      if balance_details["Available"] and balance_details["Available"] > 0.0: #purchased coins
        orders_history_url = get_url(URI_account, action = "market_orders_history", market = market_name)
        orders_history = call_secret_api(orders_history_url)
        net_value = 0.0
        for order in orders_history:
          net_value += order["Price"] if order["OrderType"] == "LIMIT_BUY" else 0
          net_value -= order["Price"] if order["OrderType"] == "LIMIT_SELL" else 0

        if net_value > 0: # buys are more, we need to get more than this net value by selling available coins
          sell_price = (net_value + net_value*profit_rate)/balance_details["Available"]
          sell_price = "%.8f" % sell_price
          sell_limit_url = get_url(URI_market, action = "sell", market = market_name, quantity = balance_details["Available"], rate = sell_price)
          order_placed = call_secret_api(sell_limit_url)
          print order_placed, "for #%s at #%s" %(market_name,sell_price)
        expected_worth += (net_value + net_value*profit_rate)
  print("Expected Worth=" +  expected_worth)

def get_market_summary(market_name):
  market_summary_url = get_url(URI_public, action = "market_day_summary", market = market_name)
  summary = call_api(market_summary_url)[0]
  return [summary["Low"], summary["Last"], summary["Ask"], summary["BaseVolume"]]

def buy_chunk(last_price, market_name, percent_increase, chunk):
  unit_price = last_price + last_price * percent_increase
  quantity = chunk/unit_price
  buy_limit_url = get_url(URI_market, action = "buy", market = market_name, quantity = quantity, rate = unit_price)
  print Fore.LIGHTYELLOW_EX + "Purchasing coin..." + Fore.WHITE
  print {"api_type" : "market", "action" : "buy", "market" : market_name, "quantity" : quantity, "rate" : unit_price}
  order = call_secret_api(buy_limit_url)
  print Fore.GREEN + "Success" if order is not None and order["uuid"] is not None else Fore.RED + "Fail"
  cnt = 1
  while cnt <= 3 and  order is not None and order["uuid"] is not None: #retry
    print Fore.YELLOW + "Retry #{cnt}: Purchasing coin..." + Fore.WHITE
    sleep(1) # half second
    order = call_secret_api(buy_limit_url)
    print Fore.GREEN + "Success" if order is not None and order["uuid"] is not None else Fore.RED + "Fail"
    cnt += 1
  global units_bought
  units_bought = quantity if order is not None and order["uuid"] is not None else 0
  return order

# method to place BUY order
# params: 
# percent_increase(float) - BUY price will be percent_increase of last_price of the market i.e BUY_PRICE = (1.0 + percent_increase)*last_price
# chunk(float) - Amount of BTC to invest for buying altcoin i.e BUY IF [last_price < (1.0 + prepump_buffer)*low_24_hr]
# prepump_buffer(float) -  Allowed buffer for prepump
def buy_bot(percent_increase = 0.05, chunk = 0.006, prepump_buffer = 0.5):
  global market_name
  market_name = market_name
  low_24_hr, last_price, ask_price, volume = get_market_summary(market_name)
  total_spent = 0.0
  print {"low_24_hr" : low_24_hr, "last_price" : last_price, "ask_price" : ask_price, "volume" : volume}
  if volume < 100 and last_price < (1.0 + prepump_buffer) * low_24_hr: #last_price is smaller than 50% increase since yerterday
    print Fore.BLUE + "Coin is not prepumped" + Fore.WHITE
    order = buy_chunk(last_price, market_name, percent_increase, chunk)
    print order, "Units Bought : #{%s}" %(units_bought)

# method to BUY all low volume coins
# params: 
# percent_increase(float) - BUY price will be percent_increase of last_price of the market i.e BUY_PRICE = (1.0 + percent_increase)*last_price
# chunk(float) - Amount of BTC to invest for buying altcoin i.e BUY IF [last_price < (1.0 + prepump_buffer)*low_24_hr]
# prepump_buffer(float) -  Allowed buffer for prepump
def buy_all_bot(percent_increase = 0.05, chunk = 0.006, prepump_buffer = 0.5):
  markets_url = get_url(URI_public, action = "markets")
  markets = call_api(markets_url)
  global currency
  for market in markets:
    currency = market["MarketCurrency"]
    base_currency = market["BaseCurrency"]
    market_name = market["MarketName"]
    if market["IsActive"] and base_currency == "BTC":
      market_name = market_name
      buy_bot(percent_increase, chunk, prepump_buffer)

# method to place SELL order
# params:
# percent_decrease(float) - BUY price will be percent_decrease of last_price of the market, eg. SELL_PRICE = (1.0 - percent_decrease)*last_price
def sell_bot(percent_decrease = 0.1):
  global market_name
  market_name = market_name
  global currency
  currency = currency
  low_24_hr, last_price, ask_price, volume = get_market_summary(market_name)
  sell_price = last_price - percent_decrease*last_price
  get_balance_url = get_url(URI_account, action = "currency_balance", currency = currency)
  balance_details = call_secret_api(get_balance_url)
  sell_price = "%.8f" % sell_price
  if balance_details and balance_details["Available"] and balance_details["Available"] > 0.0:
    print [market_name, last_price, balance_details["Available"], sell_price]
    sell_limit_url = get_url(URI_market, action = "sell", market = market_name, quantity = balance_details["Available"], rate = sell_price)
    print Fore.YELLOW, "Selling coin..." 
    print {api_type : "market", action : "sell", market : market_name, quantity : balance_details["Available"], rate : sell_price}
    order_placed = call_secret_api(sell_limit_url)
    print (Fore.GREEN + "Success" if order_placed and order_placed["uuid"] is not None else "Fail")
    cnt = 1
    while cnt <= 3 and order_placed and order_placed["uuid"] is None: #retry
      print Fore.YELLOW, "Retry #{cnt} : Selling coin..."
      sleep(1) # half second
      order_placed = call_secret_api(sell_limit_url)
      print Fore.GREEN + "Success" if order_placed and order_placed["uuid"] is not None else Fore.RED + "Failed"
      cnt += 1
      
    print order_placed,"Sell #{%s} of #{%s} at #{%s}" %(balance_details["Available"],market_name,sell_price)
  else:
    print Fore.RED,"Insufficient Balance"


# method to place BUY and SELL order immediately after purchase
# params :
# percent_increase(float)  ->  BUY_PRICE = (1.0 + percent_increase) * last_price
# chunk(float)  -> Amount of BTC to invest for buying altcoin
# prepump_buffer(float) -  Allowed buffer for prepump
# profit(float) -> SELL_PRICE = (1.0 + profit) * BUY_PRICE
# splits(int) -> How many splits of available quantity you want to make [profit] increment each time in next sell order
def buy_sell_bot(percent_increase = 0.05, chunk = 0.004, prepump_buffer = 0.5, profit = 0.2, splits = 2, no_of_retries = 10):
  global market_name
  market_name = market_name
  global currency
  currency = currency
  low_24_hr, last_price, ask_price, volume = get_market_summary(market_name)
  total_spent = 0.0
  print {"low_24_hr" : low_24_hr, "last_price" : last_price, "ask_price" : ask_price}
  if last_price < (1.0 + prepump_buffer)*low_24_hr: #last_price is smaller than 50% increase since yerterday
    order = buy_chunk(last_price, market_name, percent_increase, chunk)
    buy_price = last_price + last_price * percent_increase
    counter = 0
    while counter < no_of_retries:
      get_balance_url = get_url(URI_account, action = "currency_balance", currency = currency)
      balance_details = call_secret_api(get_balance_url)
      print balance_details
      if balance_details and balance_details["Available"] and balance_details["Available"] > 0.0: # available coins present
        qty = balance_details["Available"]/splits
        for i in range(splits):
          qty += (int(balance_details["Available"]) % splits) if (i-1 == splits) else 0
          sell_price = buy_price + buy_price * (profit * (i+1))
          sell_price = "%.8f" % sell_price
          sell_limit_url = get_url(URI_market, action = "sell", market = market_name, quantity = qty, rate = sell_price)
          print Fore.YELLOW, "Selling coin..."
          print {"api_type" : "market", "action" : "sell", "market" : market_name, "quantity" : qty, "rate" : sell_price}
          order_placed = call_secret_api(sell_limit_url)
          print Fore.GREEN + "Success" if(order_placed and order_placed["uuid"] is not None) else Fore.RED + "Failed"
          cnt = 1
          while cnt <= 3 and order_placed and order_placed["uuid"] is None: #retry
            print Fore.YELLOW,"Retry #{cnt} : Selling coin..."
            sleep(1) # half second
            order_placed = call_secret_api(sell_limit_url)
            print Fore.GREEN + "Success" if(order_placed and order_placed["uuid"] is not None) else Fore.RED + "Failed"
            cnt += 1
          
          print order_placed, "Sell #{%s} of #{%s} at #{%s}" %(qty,market_name,sell_price)
        break
      counter += 1
      sleep(0.5)

# method to place SELL order by cancelling all open orders
# params:
# percent_decrease(float) - BUY price will be percent_decrease of last_price of the market, eg. SELL_PRICE = (1.0 - percent_decrease)*last_price
def sell_at_any_cost(percent_decrease = 0.3):
  global market_name
  market_name = market_name
  open_orders_url = get_url(URI_market, action = "open_orders", market = market_name)
  open_orders = call_secret_api(open_orders_url)
  #cancel all orders
  if open_orders.size > 0:
    for open_order in open_orders:
      cancel_order_url = get_url(URI_market, action = "cancel_by_uuid", uuid = open_order["OrderUuid"])
      call_secret_api(cancel_order_url)
  # call sell bot again with lower profit
  sell_order = sell_bot(percent_decrease)


global BOT_TYPE
if BOT_TYPE == 1: buy_bot(0.05, 0.006, 0.5)
if BOT_TYPE == 2: sell_order = sell_bot(0.1) 
if BOT_TYPE == 3: buy_sell_bot(0.05, 0.012, 0.5, 0.1, 2) 
if BOT_TYPE == 4: sell_at_any_cost(0.3) 
if BOT_TYPE == 5: buy_all_bot(0.05, 0.006, 0.5) 
if BOT_TYPE == 6: sell_all_bot(0.2) 
if BOT_TYPE == 7: cancel_all_bot 



