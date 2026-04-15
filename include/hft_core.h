#pragma once
#include <map>
#include <vector>
#include <string>

// Represents a single order in the market
// In real HFT systems, this would also include timestamp, exchange info, etc.
struct Order {
    uint64_t id;        // Unique order identifier
    double price;       // Quote price (what we posted)
    double fill_price;  // Actual execution price (may differ due to slippage)
    int quantity;       // Number of contracts/shares
    int filled_qty;     // Actual quantity filled
    bool is_buy;        // true = buy order, false = sell order
};

// Represents a price level in the order book (for display/analysis)
struct Level {
    double price;
    int quantity;
};

// Order book structure storing all bids and asks
// bids: sorted by price descending (best bid first)
// asks: sorted by price ascending (best ask first)
struct OrderBook {
    std::map<double, int, std::greater<double>> bids;  // Price -> quantity
    std::map<double, int> asks;
};

// Handles incoming market data and maintains order book state
class MarketDataHandler {
public:
    // Update bid/ask price level (quantity=0 removes the level)
    void update_bid(double price, int quantity);
    void update_ask(double price, int quantity);
    
    // Get current market prices
    double get_best_bid() const;    // Highest buy price
    double get_best_ask() const;   // Lowest sell price
    double get_mid_price() const;   // (best_bid + best_ask) / 2
    double get_spread() const;      // best_ask - best_bid
    
    const OrderBook& get_order_book() const { return order_book_; }
    
private:
    OrderBook order_book_;
};

// Simple market maker that quotes inside the spread
// Strategy: post buy inside bid, sell inside ask - compete for order flow
// inside_pct: how deep into the spread (0.0=edge/most aggressive, 0.5=mid, 1.0=crossed)
//   - Lower values: closer to market edge, more fills (queue priority), less profit per fill
//   - Higher values: closer to mid, fewer fills, more profit per fill
class SimpleMarketMaker {
public:
    SimpleMarketMaker(double inside_pct, int quantity)
        : inside_pct_(inside_pct), quantity_(quantity) {}
    
    // Generate buy/sell orders inside the current spread
    // Buy price = best_bid + (spread * inside_pct / 2)
    // Sell price = best_ask - (spread * inside_pct / 2)
    std::pair<Order, Order> generate_quotes(const MarketDataHandler& market);
    
    // Generate quotes with slippage simulation
    // slippage_bps: slippage in basis points (1 bps = 0.01%)
    // e.g., slippage_bps=5 means 0.05% adverse price movement
    std::pair<Order, Order> generate_quotes_with_slippage(
        const MarketDataHandler& market, 
        double slippage_bps
    );
    
private:
    double inside_pct_;  // How deep inside the spread (0.0=edge/most aggressive, 0.5=mid, 1.0=crossed)
    int quantity_;       // Size of each quote
};
