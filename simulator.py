"""
Order Book Simulator for Market Making Strategy Testing.

Simulates realistic market dynamics including:
- Mid-price evolution (geometric Brownian motion with optional mean reversion)
- Probabilistic fill model based on queue priority (quotes near the edge fill more often)
- Adverse selection (fills tend to precede price moves against the MM)
- Inventory, cash, and P&L tracking
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Fill:
    timestamp: int
    side: str
    price: float
    qty: int
    quote_price: float


@dataclass
class MarketSnapshot:
    timestamp: int
    mid_price: float
    best_bid: float
    best_ask: float
    spread: float
    mm_buy_price: float
    mm_sell_price: float


class OrderBookSimulator:
    """
    Realistic order book simulator for testing market making strategies.

    The market maker posts buy and sell quotes inside the spread each step.
    Market orders arrive randomly and may fill the MM's quotes based on
    how close the quotes are to the market edge (queue priority: closer = more fills).

    Parameters
    ----------
    initial_mid : float
        Starting mid price.
    tick_size : float
        Minimum price increment.
    base_spread_bps : float
        Baseline spread in basis points (e.g., 5.0 means 0.05%).
    volatility : float
        Per-step standard deviation of mid-price changes (in price units).
    mean_reversion : float
        Strength of mean reversion to initial_mid (0 = random walk).
    fill_rate : float
        Base probability of a fill per market order (arrival-adjusted).
        Higher = more fills. Actual fill probability also depends on inside_pct
        (lower inside_pct = closer to edge = higher effective fill rate).
    adverse_selection_bps : float
        After a fill, the mid price shifts against the MM by this many bps.
        Models informed traders confirming the adverse selection problem.
    market_order_rate : float
        Average number of market orders per step per side (Poisson).
    seed : int, optional
        Random seed for reproducibility.
    """

    def __init__(
        self,
        initial_mid: float = 100.0,
        tick_size: float = 0.01,
        base_spread_bps: float = 5.0,
        volatility: float = 0.02,
        mean_reversion: float = 0.0,
        fill_rate: float = 0.15,
        adverse_selection_bps: float = 0.5,
        market_order_rate: float = 1.0,
        seed: Optional[int] = None,
    ):
        self.initial_mid = initial_mid
        self.tick_size = tick_size
        self.base_spread_bps = base_spread_bps
        self.volatility = volatility
        self.mean_reversion = mean_reversion
        self.fill_rate = fill_rate
        self.adverse_selection_bps = adverse_selection_bps
        self.market_order_rate = market_order_rate

        self.rng = np.random.default_rng(seed)

        self.mid_price = initial_mid
        self.time = 0
        self.cash = 0.0
        self.inventory = 0
        self.fills: List[Fill] = []
        self.snapshots: List[MarketSnapshot] = []
        self.pnl_history: List[float] = []
        self.inventory_history: List[int] = []

    def _current_spread(self) -> float:
        return self.mid_price * self.base_spread_bps / 10000.0

    def _evolve_price(self, adverse_drift: float = 0.0) -> None:
        noise = self.rng.normal(0, self.volatility)
        reversion = self.mean_reversion * (self.initial_mid - self.mid_price)
        self.mid_price = max(1.0, self.mid_price + noise + reversion + adverse_drift)

    def _fill_probability(self, inside_pct: float) -> float:
        """
        Fill probability per market order arrival.

        Quotes placed near the edge (lower inside_pct) get filled more often because
        they have queue priority — market orders hit the best available price first.
        Quotes near the mid (higher inside_pct) offer better prices to counterparties
        but are deeper in the book and receive less order flow.
            inside_pct=0.0 (at market): P = fill_rate
            inside_pct=0.5 (at mid):     P = fill_rate * 0.3
            inside_pct=1.0 (crossed):    P ≈ fill_rate * 0.01

        The relationship is exponential: deeper in the book = exponentially less likely to fill.
        """
        aggressiveness = max(0.0, 1.0 - inside_pct)
        return self.fill_rate * (aggressiveness ** 2)

    def step(self, inside_pct: float = 0.2, mm_qty: int = 50) -> dict:
        """
        Run one simulation step.

        1. Mid price evolves (GBM + mean reversion + adverse selection)
        2. MM places buy/sell quotes inside the spread
        3. Market orders arrive and may fill MM quotes
        4. MM state (cash, inventory) is updated

        Parameters
        ----------
        inside_pct : float
            How deep inside the spread the MM quotes.
            0=at market edge (most aggressive, most fills),
            0.5=at mid (moderate),
            1=crossed (suicidal, almost no fills).
        mm_qty : int
            Order size for each MM quote.

        Returns
        -------
        dict with current step info.
        """
        self.time += 1

        # 1. Evolve mid price
        self._evolve_price()

        # 2. Current market state
        spread = self._current_spread()
        best_bid = round(self.mid_price - spread / 2, 2)
        best_ask = round(self.mid_price + spread / 2, 2)

        # 3. MM quote prices
        inside_amount = spread * inside_pct
        mm_buy_price = round(best_bid + inside_amount / 2, 2)
        mm_sell_price = round(best_ask - inside_amount / 2, 2)

        # 4. Determine fills from market order flow
        fill_prob = self._fill_probability(inside_pct)
        n_buy_orders = self.rng.poisson(self.market_order_rate)
        n_sell_orders = self.rng.poisson(self.market_order_rate)

        buy_filled = 0
        sell_filled = 0
        buy_fill_price = mm_buy_price
        sell_fill_price = mm_sell_price

        # Market sell orders may fill MM's buy quote
        for _ in range(n_sell_orders):
            if self.rng.random() < fill_prob and buy_filled == 0:
                buy_filled = mm_qty
                # Slippage: fill price slightly worse than quote
                slippage = self.rng.exponential(spread * 0.05)
                buy_fill_price = mm_buy_price + slippage

        # Market buy orders may fill MM's sell quote
        for _ in range(n_buy_orders):
            if self.rng.random() < fill_prob and sell_filled == 0:
                sell_filled = mm_qty
                slippage = self.rng.exponential(spread * 0.05)
                sell_fill_price = mm_sell_price - slippage

        # 5. Adverse selection: price tends to move against filled MM
        adverse_drift = 0.0
        if buy_filled > 0:
            adverse_drift -= self.mid_price * self.adverse_selection_bps / 10000.0
        if sell_filled > 0:
            adverse_drift += self.mid_price * self.adverse_selection_bps / 10000.0

        if adverse_drift != 0.0:
            self.mid_price = max(1.0, self.mid_price + adverse_drift)

        # 6. Update MM state
        if buy_filled > 0:
            self.cash -= buy_fill_price * buy_filled
            self.inventory += buy_filled
            self.fills.append(Fill(self.time, 'buy', buy_fill_price, buy_filled, mm_buy_price))

        if sell_filled > 0:
            self.cash += sell_fill_price * sell_filled
            self.inventory -= sell_filled
            self.fills.append(Fill(self.time, 'sell', sell_fill_price, sell_filled, mm_sell_price))

        # 7. Record snapshot
        self.snapshots.append(MarketSnapshot(
            self.time, self.mid_price, best_bid, best_ask, spread,
            mm_buy_price, mm_sell_price,
        ))
        self.pnl_history.append(self.cash + self.inventory * self.mid_price)
        self.inventory_history.append(self.inventory)

        return {
            'time': self.time,
            'mid_price': self.mid_price,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': spread,
            'mm_buy_price': mm_buy_price,
            'mm_sell_price': mm_sell_price,
            'buy_filled': buy_filled > 0,
            'sell_filled': sell_filled > 0,
        }

    @property
    def mark_to_market_pnl(self) -> float:
        mid = self.snapshots[-1].mid_price if self.snapshots else self.mid_price
        return self.cash + self.inventory * mid

    @property
    def realized_pnl(self) -> float:
        return self.cash

    def reset(self) -> None:
        self.mid_price = self.initial_mid
        self.time = 0
        self.cash = 0.0
        self.inventory = 0
        self.fills = []
        self.snapshots = []
        self.pnl_history = []
        self.inventory_history = []

    def run(self, n_steps: int, inside_pct: float = 0.2, mm_qty: int = 50) -> List[dict]:
        """
        Run simulation for n_steps.

        Parameters
        ----------
        n_steps : int
            Number of time steps to simulate.
        inside_pct : float
            MM quote depth in spread (0=edge/most aggressive, 0.5=mid, 1=crossed).
        mm_qty : int
            Order size for each MM quote.

        Returns
        -------
        list of per-step result dicts.
        """
        self.reset()
        results = []
        for _ in range(n_steps):
            results.append(self.step(inside_pct, mm_qty))
        return results

    def get_fills_dataframe(self):
        import pandas as pd
        if not self.fills:
            return pd.DataFrame()
        data = {
            'time': [f.timestamp for f in self.fills],
            'side': [f.side for f in self.fills],
            'price': [f.price for f in self.fills],
            'qty': [f.qty for f in self.fills],
            'quote_price': [f.quote_price for f in self.fills],
            'slippage': [f.price - f.quote_price if f.side == 'buy' else f.quote_price - f.price
                         for f in self.fills],
        }
        return pd.DataFrame(data)

    def get_snapshot_dataframe(self):
        import pandas as pd
        data = {
            'time': [s.timestamp for s in self.snapshots],
            'mid_price': [s.mid_price for s in self.snapshots],
            'best_bid': [s.best_bid for s in self.snapshots],
            'best_ask': [s.best_ask for s in self.snapshots],
            'spread': [s.spread for s in self.snapshots],
            'mm_buy_price': [s.mm_buy_price for s in self.snapshots],
            'mm_sell_price': [s.mm_sell_price for s in self.snapshots],
            'pnl': self.pnl_history,
            'inventory': self.inventory_history,
        }
        return pd.DataFrame(data)