"""
Order Book Simulator for Market Making Strategy Testing.

Simulates realistic market dynamics including:
- Mid-price evolution (geometric Brownian motion with optional mean reversion)
- Probabilistic fill model based on queue priority (quotes near the edge fill more often)
- Adverse selection (fills tend to precede price moves against the MM)
- Network I/O simulation (latency, jitter, message loss, reconnection)
- Inventory, cash, and P&L tracking
"""

import numpy as np
from dataclasses import dataclass, field
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


@dataclass
class NetworkEvent:
    timestamp: int
    event_type: str  # 'latency', 'message_loss', 'reconnect', 'stale_data'
    delay_steps: int  # How many steps delayed (0 for loss/reconnect)
    detail: str  # Human-readable description


class NetworkIO:
    """
    Simulates network I/O effects on market making.

    In real HFT systems, the MM communicates with the exchange over a network.
    This class models three key network impairments:

    1. **Latency** — delay between sending an order and the exchange processing it.
       The MM sees stale market data and its quotes arrive late.
       Latency is drawn from a mixture of a fast path (low baseline) and
       occasional slow paths (GC pauses, TCP retransmits).

    2. **Message loss** — orders or market data updates that never arrive.
       UDP-based feeds can drop packets; TCP retransmits add latency.
       Modeled as a per-step probability that outgoing quotes are lost entirely.

    3. **Reconnection** — occasional disconnections requiring a reconnect period
       during which the MM cannot post quotes or receive fills.

    Parameters
    ----------
    base_latency_steps : float
        Median one-way latency in simulation steps (e.g., 1.0 = 1 step delay).
    jitter_steps : float
        Standard deviation of latency jitter per step.
    slow_path_prob : float
        Probability per step of hitting a slow network path (spike in latency).
    slow_path_latency : float
        Latency in steps when a slow path event occurs.
    message_loss_prob : float
        Probability per step that the MM's outgoing quote is lost (never reaches exchange).
    reconnect_prob : float
        Probability per step of a disconnection event.
    reconnect_duration : int
        Number of steps the MM is disconnected before reconnecting.
    seed : int, optional
        Random seed (shared with parent simulator if not provided).
    """

    def __init__(
        self,
        base_latency_steps: float = 1.0,
        jitter_steps: float = 0.5,
        slow_path_prob: float = 0.02,
        slow_path_latency: float = 10.0,
        message_loss_prob: float = 0.01,
        reconnect_prob: float = 0.001,
        reconnect_duration: int = 20,
        seed: Optional[int] = None,
    ):
        self.base_latency_steps = base_latency_steps
        self.jitter_steps = jitter_steps
        self.slow_path_prob = slow_path_prob
        self.slow_path_latency = slow_path_latency
        self.message_loss_prob = message_loss_prob
        self.reconnect_prob = reconnect_prob
        self.reconnect_duration = reconnect_duration

        self.rng = np.random.default_rng(seed)

        self.events: List[NetworkEvent] = []
        self.disconnect_remaining = 0
        self.total_latency_steps = 0
        self.total_messages_lost = 0
        self.total_reconnects = 0
        self.total_steps_active = 0
        self.latency_history: List[int] = []
        self.connected_history: List[bool] = []

    def step(self) -> dict:
        """
        Simulate one step of network I/O.

        Returns
        -------
        dict with keys:
            latency_steps : int — one-way latency for this step (0 = no delay)
            quote_lost : bool — whether the MM's outgoing quote was lost
            connected : bool — whether the MM is connected this step
            stale_data : bool — whether the MM is acting on stale market data
        """
        # Check reconnection state
        if self.disconnect_remaining > 0:
            self.disconnect_remaining -= 1
            self.latency_history.append(0)
            self.connected_history.append(False)
            return {
                'latency_steps': 0,
                'quote_lost': True,
                'connected': False,
                'stale_data': True,
            }

        self.total_steps_active += 1

        # Compute latency
        latency = max(0, round(self.rng.normal(self.base_latency_steps, self.jitter_steps)))

        # Slow path event (GC pause, TCP retransmit, etc.)
        if self.rng.random() < self.slow_path_prob:
            latency = max(latency, round(self.rng.exponential(self.slow_path_latency)))
            self.events.append(NetworkEvent(
                self.total_steps_active, 'latency', latency,
                f'Slow path: {latency}-step delay'
            ))

        self.total_latency_steps += latency

        # Message loss
        quote_lost = self.rng.random() < self.message_loss_prob
        if quote_lost:
            self.total_messages_lost += 1
            self.events.append(NetworkEvent(
                self.total_steps_active, 'message_loss', 0,
                'Outgoing quote lost in transit'
            ))

        # Reconnection event
        if self.rng.random() < self.reconnect_prob:
            self.disconnect_remaining = self.reconnect_duration
            self.total_reconnects += 1
            self.events.append(NetworkEvent(
                self.total_steps_active, 'reconnect', self.reconnect_duration,
                f'Disconnected for {self.reconnect_duration} steps'
            ))

        stale_data = latency > 0

        self.latency_history.append(latency)
        self.connected_history.append(True)

        return {
            'latency_steps': latency,
            'quote_lost': quote_lost,
            'connected': True,
            'stale_data': stale_data,
        }

    def reset(self) -> None:
        self.events = []
        self.disconnect_remaining = 0
        self.total_latency_steps = 0
        self.total_messages_lost = 0
        self.total_reconnects = 0
        self.total_steps_active = 0
        self.latency_history = []
        self.connected_history = []

    @property
    def avg_latency(self) -> float:
        active = [l for l, c in zip(self.latency_history, self.connected_history) if c]
        return np.mean(active) if active else 0.0

    @property
    def loss_rate(self) -> float:
        n = len(self.latency_history)
        return self.total_messages_lost / n if n > 0 else 0.0

    @property
    def uptime_pct(self) -> float:
        n = len(self.connected_history)
        if n == 0:
            return 100.0
        return sum(self.connected_history) / n * 100.0


class OrderBookSimulator:
    """
    Realistic order book simulator for testing market making strategies.

    The market maker posts buy and sell quotes inside the spread each step.
    Market orders arrive randomly and may fill the MM's quotes based on
    how close the quotes are to the market edge (queue priority: closer = more fills).

    Optionally includes network I/O simulation via the ``network`` parameter,
    which models latency, message loss, and reconnection events.

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
    network : NetworkIO, optional
        Network I/O simulator. If provided, latency/message loss/disconnection
        affect the MM's ability to post quotes and receive fills.
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
        network: Optional[NetworkIO] = None,
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
        self.network = network

        self.rng = np.random.default_rng(seed)

        self.mid_price = initial_mid
        self.time = 0
        self.cash = 0.0
        self.inventory = 0
        self.fills: List[Fill] = []
        self.snapshots: List[MarketSnapshot] = []
        self.pnl_history: List[float] = []
        self.inventory_history: List[int] = []
        self._price_buffer: List[float] = []

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
        2. Network I/O is simulated (latency, message loss, disconnection)
        3. MM places buy/sell quotes (possibly based on stale data)
        4. Market orders arrive and may fill MM quotes (unless disconnected/quote lost)
        5. MM state (cash, inventory) is updated

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

        # 2. Simulate network I/O
        net_state = self.network.step() if self.network else None
        connected = net_state['connected'] if net_state else True
        quote_lost = net_state['quote_lost'] if net_state else False
        latency_steps = net_state['latency_steps'] if net_state else 0
        stale_data = net_state['stale_data'] if net_state else False

        # 3. Determine the mid price the MM sees (stale if latency > 0)
        if stale_data and latency_steps > 0 and len(self._price_buffer) > latency_steps:
            lag_idx = len(self._price_buffer) - latency_steps
            mm_visible_mid = self._price_buffer[lag_idx]
        else:
            mm_visible_mid = self.mid_price

        self._price_buffer.append(self.mid_price)

        # 4. Current market state (true values for snapshot)
        spread = self._current_spread()
        best_bid = round(self.mid_price - spread / 2, 2)
        best_ask = round(self.mid_price + spread / 2, 2)

        # MM computes quotes based on what it sees (possibly stale)
        stale_spread = mm_visible_mid * self.base_spread_bps / 10000.0
        stale_bid = round(mm_visible_mid - stale_spread / 2, 2)
        stale_ask = round(mm_visible_mid + stale_spread / 2, 2)

        inside_amount = stale_spread * inside_pct
        mm_buy_price = round(stale_bid + inside_amount / 2, 2)
        mm_sell_price = round(stale_ask - inside_amount / 2, 2)

        # 5. Determine fills from market order flow
        #    No fills if: disconnected, quote lost, or disconnected
        buy_filled = 0
        sell_filled = 0
        buy_fill_price = mm_buy_price
        sell_fill_price = mm_sell_price

        if connected and not quote_lost:
            fill_prob = self._fill_probability(inside_pct)
            n_buy_orders = self.rng.poisson(self.market_order_rate)
            n_sell_orders = self.rng.poisson(self.market_order_rate)

            # Market sell orders may fill MM's buy quote
            for _ in range(n_sell_orders):
                if self.rng.random() < fill_prob and buy_filled == 0:
                    buy_filled = mm_qty
                    slippage = self.rng.exponential(spread * 0.05)
                    buy_fill_price = mm_buy_price + slippage

            # Market buy orders may fill MM's sell quote
            for _ in range(n_buy_orders):
                if self.rng.random() < fill_prob and sell_filled == 0:
                    sell_filled = mm_qty
                    slippage = self.rng.exponential(spread * 0.05)
                    sell_fill_price = mm_sell_price - slippage

        # 6. Adverse selection: price tends to move against filled MM
        adverse_drift = 0.0
        if buy_filled > 0:
            adverse_drift -= self.mid_price * self.adverse_selection_bps / 10000.0
        if sell_filled > 0:
            adverse_drift += self.mid_price * self.adverse_selection_bps / 10000.0

        if adverse_drift != 0.0:
            self.mid_price = max(1.0, self.mid_price + adverse_drift)

        # 7. Update MM state
        if buy_filled > 0:
            self.cash -= buy_fill_price * buy_filled
            self.inventory += buy_filled
            self.fills.append(Fill(self.time, 'buy', buy_fill_price, buy_filled, mm_buy_price))

        if sell_filled > 0:
            self.cash += sell_fill_price * sell_filled
            self.inventory -= sell_filled
            self.fills.append(Fill(self.time, 'sell', sell_fill_price, sell_filled, mm_sell_price))

        # 8. Record snapshot
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
            'connected': connected,
            'quote_lost': quote_lost,
            'stale_data': stale_data,
            'latency_steps': latency_steps,
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
        self._price_buffer = []
        if self.network:
            self.network.reset()

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
        if self.network:
            data['latency'] = self.network.latency_history
            data['connected'] = self.network.connected_history
        return pd.DataFrame(data)

    def get_network_events_dataframe(self):
        import pandas as pd
        if not self.network or not self.network.events:
            return pd.DataFrame()
        data = {
            'time': [e.timestamp for e in self.network.events],
            'event_type': [e.event_type for e in self.network.events],
            'delay_steps': [e.delay_steps for e in self.network.events],
            'detail': [e.detail for e in self.network.events],
        }
        return pd.DataFrame(data)