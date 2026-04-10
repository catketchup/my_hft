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
    // inside_pct=0.0: quotes at market (buy=bid, sell=ask)
    // inside_pct=0.5: quotes at mid-price
    // inside_pct=1.0: quotes at edge of spread (buy=ask, sell=bid) - suicidal!
    double inside_amount = spread * inside_pct_;
    
    // Buy above best bid, sell below best ask
    Order buy_order{order_id++, best_bid + inside_amount / 2, quantity_, true};
    Order sell_order{order_id++, best_ask - inside_amount / 2, quantity_, false};

    return {buy_order, sell_order};
}
