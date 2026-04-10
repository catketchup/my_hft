# HFT Core Library

A minimal, pedagogical C++ market making library with Python bindings.

## What It Does

This library implements a simple **market maker** - a trading entity that provides liquidity by always being willing to buy or sell an asset.

### Core Concepts

| Term | Definition |
|------|------------|
| **Bid** | Best price someone will buy at |
| **Ask** | Best price someone will sell at |
| **Spread** | Ask - Bid (market maker's potential profit) |
| **Mid Price** | (Bid + Ask) / 2 (fair value estimate) |
| **Round-Trip** | Buy then sell (or vice versa) |

### How Market Making Works

```
Market:           Bid=100.00, Ask=100.05
Market Maker:      Buy@100.005, Sell@100.045

Step 1: MM buys at 100.005
Step 2: MM sells at 100.045
Profit: $0.04/share
```

The market maker profits from the spread while providing liquidity to the market.

## Project Structure

```
my_hft/
├── CMakeLists.txt           # Build configuration
├── include/
│   └── hft_core.h           # Core classes (OrderBook, MarketMaker)
├── src/
│   └── order_book.cpp       # Implementation
├── python/
│   └── bindings.cpp         # pybind11 Python bindings
├── build/                   # Compiled module (after make)
├── example.py               # Simple usage example
├── hft_demo.ipynb           # Jupyter notebook with visualizations
└── README.md
```

## Build

```bash
mkdir build && cd build
cmake -DCMAKE_PREFIX_PATH=/home/hongbo/tools/anaconda3/lib/python3.12/site-packages ..
make
```

The module `hft_core.cpython-312-x86_64-linux-gnu.so` will be created in `build/`.

## Install (optional)

```bash
pip install -e .
```

Then import from anywhere without PYTHONPATH.

## Usage

### Python

```python
import hft_core

# Create market data handler
market = hft_core.MarketDataHandler()
market.update_bid(100.0, 100)
market.update_ask(100.05, 100)

# Create market maker (20% inside spread, 50 lot)
mm = hft_core.SimpleMarketMaker(0.2, 50)

# Generate quotes
buy, sell = mm.generate_quotes(market)
print(f"Buy @ {buy.price}, Sell @ {sell.price}")
```

### Jupyter Notebook

```bash
jupyter notebook hft_demo.ipynb
```

Includes visualizations of spread, quote positions, and trading simulations.

## Classes

### MarketDataHandler
- Tracks order book state (bids and asks)
- Calculates best bid/ask, mid price, spread

### SimpleMarketMaker
- Posts buy/sell quotes inside the spread
- `inside_pct`: how deep into the spread (0.0-1.0)
  - 0.0 = at market prices
  - 0.5 = at mid price
  - 1.0 = at opposite edges (bad idea)

### Order
- Represents a single order with id, price, quantity, side

## Limitations (Pedagogical)

This is a **simplified** demonstration. Real HFT systems include:

- Network I/O (exchange connectivity)
- Multi-threading (low-latency processing)
- Order management (tracking fills, cancellations)
- Position/risk management
- Market microstructure modeling
- Adverse selection mitigation
- Inventory management

## License

MIT
