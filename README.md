# Helios

Helios is a stock signal bot that fetches market data with `yfinance`, generates 4-hour trend-following signals, and sends ranked alerts to Telegram.

This repository is organized for GitHub publishing. Runtime behavior is centered on `st_pred.py`; `infer.py` is a legacy experimental file and is not required for the live signal bot.

## What This Project Does

- Downloads 1-hour OHLCV data with `yfinance`
- Resamples data to 4-hour candles
- Calculates `EMA20`, `EMA60`, and `RSI(14)`
- Generates `BUY`, `SELL`, or `HOLD` signals
- Applies two BUY-side filters:
  - SPY-based risk-off filter
  - Earnings window filter using Finnhub
- Sends Top-N ranked signals and a run summary to Telegram
- Stores bot state and logs in a local SQLite database

## Main Files

```text
Helios/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── docs/
│   └── PUBLISH_CHECKLIST.md
├── st_pred.py
├── infer.py
└── signals.db               # runtime-generated local DB, not committed
```

- `st_pred.py`: main production bot
- `infer.py`: legacy experimental script, not part of the Telegram bot flow
- `signals.db`: SQLite database for positions, signal logs, and earnings cache

## Strategy Summary

The bot evaluates symbols on 4-hour candles.

- `BUY`
  - `EMA20 > EMA60`
  - Last 2 closes are above `EMA20`
  - `RSI < 70`
- `SELL`
  - Close is below `EMA60`, or
  - `RSI > 75`
- `HOLD`
  - Any case that does not trigger `BUY` or `SELL`

Additional BUY filters:

- Risk-off:
  - If recent SPY 4H return is below `RISK_OFF_THRESHOLD`, BUY is blocked
- Earnings window:
  - If a symbol has earnings within `±EARNINGS_FILTER_DAYS`, BUY is blocked

## Telegram Integration

Telegram is connected through the Bot API.

- `TELEGRAM_BOT_TOKEN`: bot token
- `TELEGRAM_CHAT_ID`: destination chat ID

The bot sends:

- Signal notifications for Top-N BUY candidates
- Signal notifications for Top-N SELL candidates
- One run summary after each scheduled job

## Environment Variables

Copy `.env.example` to `.env` and fill in your real values.

```bash
cp .env.example .env
```

Key settings:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FINNHUB_API_KEY`
- `WATCHLIST`
- `RUN_EVERY_HOURS`
- `ONLY_REGULAR_MARKET_HOURS`
- `RISK_OFF_THRESHOLD`
- `EARNINGS_FILTER_DAYS`
- `TOP_N_BUY`
- `TOP_N_SELL`
- `SEND_SELL`
- `SEND_HOLD_SUMMARY`
- `DB_PATH`

## Installation

Python 3.10+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python st_pred.py
```

What happens on startup:

- The SQLite DB is initialized
- A Telegram startup message is sent
- The scheduler starts immediately
- The bot runs every `RUN_EVERY_HOURS`

## Database

The local SQLite DB stores:

- `positions`
- `signal_log`
- `earnings_cache`
- `earnings_window_fetch`

This file is runtime state and should not be committed to GitHub.

## GitHub Publishing Notes

- Do not commit `.env`
- Do not commit `signals.db`
- Review secrets before pushing
- If you want a cleaner repo history, consider removing local caches before the first commit

The provided `.gitignore` already excludes the most important local-only files.

## Notes

- `ALPACA_*` variables may exist in local `.env`, but the current production script does not use them
- `infer.py` appears to be unrelated to the active signal bot flow and can remain as legacy research code unless you decide to remove it later
