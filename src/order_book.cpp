#include "hft_core.h"

void MarketDataHandler::update_bid(double price, int quantity) {
    if (quantity == 0) {
        order_book_.bids.erase(price);
    } else {
        order_book_.bids[price] = quantity;
    }
}

void MarketDataHandler::update_ask(double price, int quantity) {
    if (quantity == 0) {
        order_book_.asks.erase(price);
    } else {
        order_book_.asks[price] = quantity;
    }
}

double MarketDataHandler::get_best_bid() const {
    return order_book_.bids.empty() ? 0.0 : order_book_.bids.begin()->first;
}

double MarketDataHandler::get_best_ask() const {
    return order_book_.asks.empty() ? 0.0 : order_book_.asks.begin()->first;
}

double MarketDataHandler::get_mid_price() const {
    double bid = get_best_bid();
    double ask = get_best_ask();
    return (bid + ask) / 2.0;
}

double MarketDataHandler::get_spread() const {
    return get_best_ask() - get_best_bid();
}

std::pair<Order, Order> SimpleMarketMaker::generate_quotes(const MarketDataHandler& market) {
    static uint64_t order_id = 1;
    
    double best_bid = market.get_best_bid();
    double best_ask = market.get_best_ask();
    double spread = market.get_spread();

    // Place quotes inside the spread
    // inside_pct=0.0: quotes at market prices (buy=bid, sell=ask) — most aggressive, most fills
    // inside_pct=0.5: quotes at mid-price
    // inside_pct=1.0: quotes crossed (buy=ask, sell=bid) — suicidal
    double inside_amount = spread * inside_pct_;
    
    // Buy above best bid, sell below best ask
    // For simple case, fill_price = quote_price and filled_qty = quantity
    Order buy_order{order_id++, best_bid + inside_amount / 2, 0, quantity_, quantity_, true};
    buy_order.fill_price = buy_order.price;
    Order sell_order{order_id++, best_ask - inside_amount / 2, 0, quantity_, quantity_, false};
    sell_order.fill_price = sell_order.price;

    return {buy_order, sell_order};
}

std::pair<Order, Order> SimpleMarketMaker::generate_quotes_with_slippage(
    const MarketDataHandler& market, 
    double slippage_bps
) {
    static uint64_t order_id = 1;
    
    double best_bid = market.get_best_bid();
    double best_ask = market.get_best_ask();
    double spread = market.get_spread();
    
    // Slippage factor: convert bps to decimal (1 bps = 0.01%)
    // e.g., slippage_bps=5 means 0.05% adverse move
    double slippage_decimal = slippage_bps / 10000.0;
    double slippage_amount = best_ask * slippage_decimal;  // Slippage in dollars

    // Quote prices (what we post)
    double inside_amount = spread * inside_pct_;
    double buy_quote = best_bid + inside_amount / 2;
    double sell_quote = best_ask - inside_amount / 2;

    // Fill prices (what we actually get)
    // For buy orders: slippage makes us pay MORE (adverse)
    // For sell orders: slippage makes us receive LESS (adverse)
    double buy_fill = buy_quote + slippage_amount;
    double sell_fill = sell_quote - slippage_amount;

    // Create orders with slippage
    Order buy_order{order_id++, buy_quote, buy_fill, quantity_, quantity_, true};
    Order sell_order{order_id++, sell_quote, sell_fill, quantity_, quantity_, false};

    return {buy_order, sell_order};
}
