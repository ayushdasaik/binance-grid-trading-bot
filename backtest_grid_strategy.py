"""
Grid Strategy Backtester
-------------------------
Author: Ayush D.

Simulates how the grid trading strategy would have performed against a
price series. Useful for tuning grid range / level count before going live.

NOTE: This script generates a synthetic, randomized price path (geometric
Brownian motion + mean-reverting noise) to demonstrate the backtest engine
and strategy behaviour. Swap `generate_synthetic_prices()` for real
historical OHLC data (e.g. from Binance's klines API) to backtest on actual
market history.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def generate_synthetic_prices(
    start_price: float = 27000,
    n_steps: int = 2000,
    volatility: float = 0.004,
    mean_reversion: float = 0.02,
    seed: int = 42,
) -> pd.Series:
    """Generate a mean-reverting random price path to simulate a ranging market
    (ideal conditions for a grid bot)."""
    rng = np.random.default_rng(seed)
    prices = [start_price]
    for _ in range(n_steps - 1):
        last = prices[-1]
        reversion = mean_reversion * (start_price - last) / start_price
        shock = rng.normal(0, volatility)
        new_price = last * (1 + reversion + shock)
        prices.append(new_price)
    return pd.Series(prices)


class GridBacktester:
    def __init__(self, prices: pd.Series, lower_price: float, upper_price: float,
                 grid_levels: int, quantity_per_grid: float):
        self.prices = prices
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.grid_levels = grid_levels
        self.quantity_per_grid = quantity_per_grid
        self.step = (upper_price - lower_price) / grid_levels
        self.grid_prices = [round(lower_price + self.step * i, 2) for i in range(grid_levels + 1)]

    def run(self):
        """
        Models real grid-bot economics: buy at level i, sell at level i+1.
        Each completed (buy -> sell) cycle locks in a fixed profit equal to
        one grid step, regardless of where price goes afterward. This is why
        grid bots are described as profiting from *oscillation* rather than
        directional moves.
        """
        position = 0.0
        realized_pnl = 0.0
        trades = 0
        equity_curve = []
        unrealized_curve = []

        n = len(self.grid_prices)
        # holding[i] = True means we currently own a unit bought at grid level i,
        # waiting to sell it at grid level i+1
        holding = [False] * (n - 1)
        buy_price_at = [None] * (n - 1)

        last_price = self.prices.iloc[0]

        for price in self.prices:
            for i in range(n - 1):
                buy_level = self.grid_prices[i]
                sell_level = self.grid_prices[i + 1]

                # Price dipped down through buy_level -> fill BUY
                if last_price > buy_level >= price and not holding[i]:
                    holding[i] = True
                    buy_price_at[i] = buy_level
                    position += self.quantity_per_grid

                # Price rose up through sell_level while holding -> fill SELL
                elif last_price < sell_level <= price and holding[i]:
                    profit = (sell_level - buy_price_at[i]) * self.quantity_per_grid
                    realized_pnl += profit
                    position -= self.quantity_per_grid
                    holding[i] = False
                    buy_price_at[i] = None
                    trades += 1

            unrealized_value = sum(
                (price - buy_price_at[i]) * self.quantity_per_grid
                for i in range(n - 1) if holding[i]
            )
            equity_curve.append(realized_pnl)
            unrealized_curve.append(realized_pnl + unrealized_value)
            last_price = price

        results = pd.DataFrame({
            "price": self.prices.values,
            "realized_pnl": equity_curve,
            "total_equity": unrealized_curve,
        })
        summary = {
            "total_trades": trades,
            "realized_pnl": realized_pnl,
            "final_total_equity": unrealized_curve[-1],
            "max_drawdown": self._max_drawdown(unrealized_curve),
            "open_position_units": position,
        }
        return results, summary

    @staticmethod
    def _max_drawdown(equity_curve):
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            dd = peak - value
            max_dd = max(max_dd, dd)
        return max_dd


def main():
    prices = generate_synthetic_prices(
        start_price=27000, n_steps=2000, volatility=0.004, mean_reversion=0.02
    )

    backtester = GridBacktester(
        prices=prices,
        lower_price=25000,
        upper_price=30000,
        grid_levels=10,
        quantity_per_grid=0.001,
    )

    results, summary = backtester.run()

    print("Backtest summary:")
    for k, v in summary.items():
        print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")

    # Plot price + equity curve
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    axes[0].plot(results["price"], color="#1f77b4", linewidth=1)
    for g in backtester.grid_prices:
        axes[0].axhline(g, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
    axes[0].set_title("Simulated BTC/USDT Price with Grid Levels")
    axes[0].set_ylabel("Price (USDT)")

    axes[1].plot(results["realized_pnl"], color="#2ca02c", linewidth=1.5, label="Realized P&L")
    axes[1].plot(results["total_equity"], color="#ff7f0e", linewidth=1, linestyle="--",
                 alpha=0.7, label="Total equity (incl. open position)")
    axes[1].set_title(f"Grid Bot P&L  |  Completed round-trips: {summary['total_trades']}  |  "
                       f"Realized profit: ${summary['realized_pnl']:.2f}")
    axes[1].set_ylabel("P&L (USDT)")
    axes[1].set_xlabel("Time step")
    axes[1].legend(loc="upper left")
    axes[1].axhline(0, color="gray", linewidth=0.7)

    plt.tight_layout()
    plt.savefig("grid_bot_backtest.png", dpi=150)
    print("\nChart saved to grid_bot_backtest.png")


if __name__ == "__main__":
    main()
