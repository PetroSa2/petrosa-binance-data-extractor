import os
import asyncio
from binance import Client

async def check_account():
    api_key = "VGK4c8SSNZtS7ATDd8ClzdgGFEffvGnaAc471nzYF43lfsBZKBcfbGTaSQFGiF0v"
    api_secret = "2NoOvkvnbpdf9qmAYlivh07Gt7t786IFkMgy20NolUKdaNpSGo2h01nNPi7cw9QH"
    
    print("Connecting to Binance Testnet...")
    client = Client(api_key, api_secret, testnet=True)
    
    # 1. Get Futures Account Balance
    print("\n1. --- Futures Account Balance ---")
    account = client.futures_account()
    assets = account.get('assets', [])
    for asset in assets:
        if asset['asset'] == 'USDT':
            print(f"Asset: {asset['asset']}")
            print(f"  Wallet Balance:    {asset['walletBalance']}")
            print(f"  Unrealized PNL:    {asset['unrealizedProfit']}")
            print(f"  Margin Balance:    {asset['marginBalance']}")
            print(f"  Available Balance: {asset['availableBalance']}")
            print(f"  Max Withdraw:      {asset['maxWithdrawAmount']}")

    # 2. Get Open Positions
    print("\n2. --- Open Positions ---")
    positions = client.futures_position_information()
    active_positions = [p for p in positions if float(p['positionAmt']) != 0]
    if not active_positions:
        print("No active positions.")
    for p in active_positions:
        print(f"Symbol: {p['symbol']} | Side: {p['positionSide']} | Amt: {p['positionAmt']} | Entry: {p['entryPrice']} | UnPnL: {p['unRealizedProfit']}")

    # 3. Get Open Orders
    print("\n3. --- Open Orders ---")
    orders = client.futures_get_open_orders()
    if not orders:
        print("No open orders.")
    for o in orders:
        print(f"Symbol: {o['symbol']} | Side: {o['side']} | Type: {o['type']} | Qty: {o['origQty']} | Price: {o['price']}")

if __name__ == "__main__":
    asyncio.run(check_account())
