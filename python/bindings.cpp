#include <pybind11/pybind11.h>
#include "hft_core.h"

namespace py = pybind11;

// Create Python module named 'hft_core'
// This exposes C++ classes to Python for use in trading strategies
PYBIND11_MODULE(hft_core, m) {
    m.doc() = "HFT Core Library - Market making and order book utilities";
    
    // Expose Order struct to Python
    // Users can access order.id, order.price, order.quantity, order.is_buy
    py::class_<Order>(m, "Order")
        .def(py::init<uint64_t, double, int, bool>())  // Constructor
        .def_readwrite("id", &Order::id)               // Make members accessible
        .def_readwrite("price", &Order::price)
        .def_readwrite("quantity", &Order::quantity)
        .def_readwrite("is_buy", &Order::is_buy);
    
    // Expose MarketDataHandler - tracks order book state
    py::class_<MarketDataHandler>(m, "MarketDataHandler")
        .def(py::init<>())  // Default constructor
        .def("update_bid", &MarketDataHandler::update_bid, "Update bid level")
        .def("update_ask", &MarketDataHandler::update_ask, "Update ask level")
        .def("get_best_bid", &MarketDataHandler::get_best_bid, "Highest bid price")
        .def("get_best_ask", &MarketDataHandler::get_best_ask, "Lowest ask price")
        .def("get_mid_price", &MarketDataHandler::get_mid_price, "(bid+ask)/2")
        .def("get_spread", &MarketDataHandler::get_spread, "ask - bid");
    
    // Expose SimpleMarketMaker - generates quotes inside the spread
    py::class_<SimpleMarketMaker>(m, "SimpleMarketMaker")
        .def(py::init<double, int>(), "inside_pct=0.5, quantity=50")
        .def("generate_quotes", &SimpleMarketMaker::generate_quotes, 
             "Generate buy/sell orders inside the spread");
}
