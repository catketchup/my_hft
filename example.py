#!/usr/bin/env python3
"""
Example usage of HFT Core Library
A simple market-making strategy demonstration

Market Making Basics:
- A market maker provides liquidity by always being willing to buy or sell
- Profit comes from the spread (difference between buy and sell prices)
- Risk: inventory risk (holding positions that move against you)
"""

import hft_core


def main():
    # Create market data handler to track order book
    market = hft_core.MarketDataHandler()
    
    # Simulate receiving market data (bid/ask quotes)
    # In real systems, this comes from exchange feed
    market.update_bid(100.0, 100)    # Someone willing to buy 100 @ 100.00
    market.update_ask(100.05, 100)   # Someone willing to sell 100 @ 100.05
    
    # Query current market state
    print("=== Current Market State ===")
    print(f"Best Bid: {market.get_best_bid()}")     # 100.00
    print(f"Best Ask: {market.get_best_ask()}")     # 100.05
    print(f"Mid Price: {market.get_mid_price()}")   # 100.025
    print(f"Spread: {market.get_spread()}")          # 0.05
    
    # Create market maker quoting 20% inside the spread
    # Lower inside_pct = closer to market edge = more aggressive = more fills
    mm = hft_core.SimpleMarketMaker(0.2, 50)  # 20% inside the spread
    
    # Generate quotes based on current market
    buy_order, sell_order = mm.generate_quotes(market)
    
    print(f"\n=== Market Maker Quotes ===")
    print(f"Buy Order:  id={buy_order.id}, price={buy_order.price:.4f}, qty={buy_order.quantity}")
    print(f"Sell Order: id={sell_order.id}, price={sell_order.price:.4f}, qty={sell_order.quantity}")
    
    # Example: If we get filled on both orders
    # Buy 50 @ 99.975, Sell 50 @ 100.075
    # Profit per round trip = 100.075 - 99.975 = 0.10 per share
    profit = sell_order.price - buy_order.price
    print(f"\nTheoretical profit per round-trip: {profit:.4f}")
    print(f"\nNote: MM quotes are INSIDE the spread (competing for order flow)")


if __name__ == "__main__":
    main()
