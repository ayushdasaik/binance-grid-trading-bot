# Binance Grid Trading Bot

A configurable grid trading bot for Binance Spot markets, with an included
backtesting engine to validate strategy parameters before going live.

## What it does

Places a ladder of buy/sell limit orders across a defined price range. As
price oscillates, each completed buy-low/sell-high cycle locks in a fixed
profit — the strategy doesn't need to predict market direction, only that
price will keep moving up and down within the chosen range.

## Files

- `binance_grid_bot.py` — Live/testnet trading bot using the official
  `python-binance` client. Builds the grid, places initial orders, and
  monitors fills to automatically refill the grid as orders complete.
- `backtest_grid_strategy.py` — Standalone backtester. Simulates the grid
  strategy against a price series and outputs a trade summary + equity
  chart (`grid_bot_backtest.png`). Ships with a synthetic mean-reverting
  price generator for demonstration — swap in real OHLC/kline data to
  backtest against actual market history.

## Sample backtest result

33 completed round-trips on a simulated ranging market, ~$16.50 realized
profit on a 10-level grid between 25,000–30,000 (0.001 BTC per grid step).
See `grid_bot_backtest.png` for the price path and P&L curve.

## Security model

- Designed to run with **trade-only API keys** — no withdrawal permission
  is ever requested or required.
- Defaults to **Binance Testnet**; live trading requires an explicit
  config change.
- API keys are read from environment variables, never hardcoded.

## Adapting to MT4/MT5

The same grid logic (price-range partitioning, buy-low/sell-high cycling,
automatic refill on fill) ports directly to MetaTrader via MQL4/MQL5 Expert
Advisors, or via a Python bridge (e.g. MetaTrader5 package) for brokers that
support it. Available on request for forex/CFD grid strategies.

## Disclaimer

This is a demonstration / portfolio project. Grid trading performs well in
ranging markets and can lose money in strong sustained trends (the bot keeps
buying dips that don't recover). Always backtest on your target asset and
use position sizing appropriate to your risk tolerance.
