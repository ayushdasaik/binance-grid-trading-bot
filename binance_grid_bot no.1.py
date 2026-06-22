"""
Binance Grid Trading Bot
-------------------------
Author: Ayush D.

A configurable grid trading bot for Binance Spot markets. Places a ladder of
buy/sell limit orders across a price range and profits from price oscillation
within that range, without needing to predict market direction.

SECURITY NOTE:
This bot is designed to run with TRADE-ONLY API keys (read + spot trade).
It never requests or uses withdrawal permissions. Always test on Binance
Testnet (https://testnet.binance.vision) before running on a live account.

Strategy logic:
1. Define a price range [lower_price, upper_price] and number of grid levels.
2. Calculate evenly spaced grid lines within that range.
3. Place a BUY limit order at every grid line below the current price,
   and a SELL limit order at every grid line above the current price.
4. When a BUY fills, place a new SELL one grid level above it.
   When a SELL fills, place a new BUY one grid level below it.
5. Repeat - this captures profit on every up/down oscillation inside the range.
"""

import time
import logging
from dataclasses import dataclass
from typing import List, Optional

from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("grid_bot")


@dataclass
class GridConfig:
    symbol: str = "BTCUSDT"
    lower_price: float = 25000.0
    upper_price: float = 30000.0
    grid_levels: int = 10
    quantity_per_grid: float = 0.001  # base asset quantity per order
    use_testnet: bool = True
    poll_interval_seconds: int = 15


class BinanceGridBot:
    def __init__(self, api_key: str, api_secret: str, config: GridConfig):
        self.config = config
        self.client = Client(api_key, api_secret, testnet=config.use_testnet)
        self.grid_prices: List[float] = []
        self.open_orders: dict = {}  # order_id -> grid price

    # ---------- Grid setup ----------

    def build_grid(self) -> List[float]:
        """Compute evenly spaced grid price levels."""
        step = (self.config.upper_price - self.config.lower_price) / self.config.grid_levels
        self.grid_prices = [
            round(self.config.lower_price + step * i, 2)
            for i in range(self.config.grid_levels + 1)
        ]
        log.info(f"Built {len(self.grid_prices)} grid levels: {self.grid_prices}")
        return self.grid_prices

    def get_current_price(self) -> float:
        ticker = self.client.get_symbol_ticker(symbol=self.config.symbol)
        return float(ticker["price"])

    # ---------- Order placement ----------

    def place_order(self, side: str, price: float) -> Optional[dict]:
        try:
            order = self.client.create_order(
                symbol=self.config.symbol,
                side=side,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=self.config.quantity_per_grid,
                price=str(price),
            )
            log.info(f"Placed {side} order at {price}: order_id={order['orderId']}")
            self.open_orders[order["orderId"]] = price
            return order
        except Exception as e:
            log.error(f"Failed to place {side} order at {price}: {e}")
            return None

    def initialize_orders(self):
        """Place initial BUY orders below current price and SELL orders above."""
        current_price = self.get_current_price()
        log.info(f"Current price: {current_price}")

        for price in self.grid_prices:
            if price < current_price:
                self.place_order(SIDE_BUY, price)
            elif price > current_price:
                self.place_order(SIDE_SELL, price)

    # ---------- Order monitoring / grid refill ----------

    def check_filled_orders(self):
        """Poll open orders, detect fills, and refill the grid."""
        try:
            open_orders = self.client.get_open_orders(symbol=self.config.symbol)
            open_ids = {o["orderId"] for o in open_orders}
        except Exception as e:
            log.error(f"Error fetching open orders: {e}")
            return

        filled_ids = [oid for oid in self.open_orders if oid not in open_ids]

        for order_id in filled_ids:
            filled_price = self.open_orders.pop(order_id)
            self._refill_grid(filled_price)

    def _refill_grid(self, filled_price: float):
        """When an order fills, place the opposite order one grid step away."""
        step = (self.config.upper_price - self.config.lower_price) / self.config.grid_levels
        idx = self.grid_prices.index(filled_price) if filled_price in self.grid_prices else None
        if idx is None:
            return

        # Heuristic: if this price was a BUY level, place a SELL one level up.
        # If it was a SELL level, place a BUY one level down.
        current_price = self.get_current_price()
        if filled_price < current_price and idx + 1 < len(self.grid_prices):
            self.place_order(SIDE_SELL, self.grid_prices[idx + 1])
        elif filled_price > current_price and idx - 1 >= 0:
            self.place_order(SIDE_BUY, self.grid_prices[idx - 1])

    # ---------- Main loop ----------

    def run(self):
        log.info(f"Starting grid bot for {self.config.symbol} "
                  f"[{self.config.lower_price} - {self.config.upper_price}], "
                  f"{self.config.grid_levels} levels, testnet={self.config.use_testnet}")
        self.build_grid()
        self.initialize_orders()

        try:
            while True:
                self.check_filled_orders()
                time.sleep(self.config.poll_interval_seconds)
        except KeyboardInterrupt:
            log.info("Shutting down bot, cancelling open orders...")
            self.shutdown()

    def shutdown(self):
        for order_id in list(self.open_orders.keys()):
            try:
                self.client.cancel_order(symbol=self.config.symbol, orderId=order_id)
                log.info(f"Cancelled order {order_id}")
            except Exception as e:
                log.error(f"Could not cancel order {order_id}: {e}")


if __name__ == "__main__":
    # Load keys from environment variables - never hardcode keys in source.
    import os

    API_KEY = os.environ.get("BINANCE_API_KEY", "")
    API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

    config = GridConfig(
        symbol="BTCUSDT",
        lower_price=25000,
        upper_price=30000,
        grid_levels=10,
        quantity_per_grid=0.001,
        use_testnet=True,
    )

    bot = BinanceGridBot(API_KEY, API_SECRET, config)
    bot.run()
