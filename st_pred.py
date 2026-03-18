import os
import time
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, Tuple, List

import requests
import numpy as np
import pandas as pd
import yfinance as yf
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None

# Optional: trading calendar for accurate +/- N trading days
try:
    import pandas_market_calendars as mcal
    HAS_MCAL = True
except Exception:
    HAS_MCAL = False

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

WATCHLIST = [s.strip().upper() for s in os.getenv(
    "WATCHLIST", "AAPL,MSFT,NVDA,TSLA,AMZN"
).split(",") if s.strip()]

RUN_EVERY_HOURS = int(os.getenv("RUN_EVERY_HOURS", "4"))
ONLY_REGULAR = os.getenv("ONLY_REGULAR_MARKET_HOURS", "1") == "1"
RISK_OFF_THRESHOLD = float(os.getenv("RISK_OFF_THRESHOLD", "-0.02"))
EARNINGS_FILTER_DAYS = int(os.getenv("EARNINGS_FILTER_DAYS", "5"))
NOTIFY_HOLD = os.getenv("NOTIFY_HOLD", "0") == "1"
TOP_N_BUY = int(os.getenv("TOP_N_BUY", "5"))
TOP_N_SELL = int(os.getenv("TOP_N_SELL", "5"))
SEND_SELL = os.getenv("SEND_SELL", "1").strip() == "1"
SEND_HOLD_SUMMARY = os.getenv("SEND_HOLD_SUMMARY", "1").strip() == "1"
DB_PATH = os.getenv("DB_PATH", "signals.db")

NY_TZ = ZoneInfo("America/New_York") if ZoneInfo else None

# def tg_send(text: str):
#     if not BOT_TOKEN or not CHAT_ID:
#         raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
#     payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
#     r = requests.post(url, json=payload, timeout=20)
#     r.raise_for_status()
def tg_send(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 429:
            # Telegram flood control
            try:
                j = r.json()
                retry = int(j.get("parameters", {}).get("retry_after", 2))
            except Exception:
                retry = 2
            print(f"[tg_send] 429 Too Many Requests. sleep {retry}s")
            time.sleep(retry)
            r = requests.post(url, json=payload, timeout=20)

        if r.status_code != 200:
            print("[tg_send] error:", r.status_code, r.text)
            return False
        return True

    except Exception as e:
        print("[tg_send] exception:", type(e).__name__, e)
        return False


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def db_init():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        status TEXT NOT NULL,              -- FLAT / LONG (확장 가능)
        last_signal TEXT NOT NULL,         -- BUY/SELL/HOLD
        last_notified_utc TEXT,
        entry_price REAL,
        stop_price REAL,
        updated_utc TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS earnings_cache (
        symbol TEXT NOT NULL,
        earnings_date TEXT NOT NULL,       -- YYYY-MM-DD
        fetched_utc TEXT NOT NULL,
        PRIMARY KEY(symbol, earnings_date)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS earnings_window_fetch (
        symbol TEXT NOT NULL,
        win_from TEXT NOT NULL,   -- YYYY-MM-DD
        win_to   TEXT NOT NULL,   -- YYYY-MM-DD
        fetched_utc TEXT NOT NULL,
        PRIMARY KEY(symbol, win_from, win_to)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS signal_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utc_time TEXT NOT NULL,
        symbol TEXT NOT NULL,
        signal TEXT NOT NULL,
        close REAL,
        ema_fast REAL,
        ema_slow REAL,
        rsi REAL,
        risk_off INTEGER NOT NULL,
        earnings_block INTEGER NOT NULL,
        note TEXT
    );
    """)
    conn.commit()
    conn.close()

def get_position(conn, symbol: str) -> Dict:
    cur = conn.cursor()
    cur.execute("SELECT symbol,status,last_signal,last_notified_utc,entry_price,stop_price,updated_utc "
                "FROM positions WHERE symbol=?", (symbol,))
    row = cur.fetchone()
    if not row:
        return {
            "symbol": symbol,
            "status": "FLAT",
            "last_signal": "HOLD",
            "last_notified_utc": None,
            "entry_price": None,
            "stop_price": None,
            "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        }
    return {
        "symbol": row[0],
        "status": row[1],
        "last_signal": row[2],
        "last_notified_utc": row[3],
        "entry_price": row[4],
        "stop_price": row[5],
        "updated_utc": row[6]
    }

def upsert_position(conn, pos: Dict):
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO positions(symbol,status,last_signal,last_notified_utc,entry_price,stop_price,updated_utc)
    VALUES(?,?,?,?,?,?,?)
    ON CONFLICT(symbol) DO UPDATE SET
        status=excluded.status,
        last_signal=excluded.last_signal,
        last_notified_utc=excluded.last_notified_utc,
        entry_price=excluded.entry_price,
        stop_price=excluded.stop_price,
        updated_utc=excluded.updated_utc;
    """, (pos["symbol"], pos["status"], pos["last_signal"], pos["last_notified_utc"],
          pos["entry_price"], pos["stop_price"], pos["updated_utc"]))
    # conn.commit()

def is_regular_market_hours_now() -> bool:
    if not NY_TZ:
        return True
    
    now_ny = datetime.now(timezone.utc).astimezone(NY_TZ)

    if now_ny.weekday() >= 5:
        return False
    if HAS_MCAL:
        nyse = mcal.get_calendar("NYSE")
        d = now_ny.date()
        sched = nyse.schedule(start_date=d, end_date=d)
        if sched.empty:
            return False
        market_open = sched.iloc[0]["market_open"].tz_convert(NY_TZ)
        market_close = sched.iloc[0]["market_close"].tz_convert(NY_TZ)
        return market_open <= now_ny <= market_close
    
    start = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
    end = now_ny.replace(hour=16, minute=0, second=0, microsecond=0)
    return start <= now_ny <= end

def fetch_1h_bars(symbol: str, period: str = "60d") -> pd.DataFrame:
    t = yf.Ticker(symbol)
    df = t.history(period=period, interval="1h", auto_adjust=False, actions=False)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume" 
    })

    if df.index.tz is None:
        df.index = df.index.tz_localize("America/New_York")
    df = df.tz_convert("UTC")

    keep = ["open", "high", "low", "close", "volume"]
    df = df[keep].dropna()
    return df

def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    if df_1h.empty:
        return df_1h
    ohlcv = df_1h.resample("4h", label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    ohlcv = ohlcv.reset_index().rename(columns={ohlcv.columns[0]: "time"})
    return ohlcv

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    return 100 - (100 / (1 + rs))

# def risk_off_now() -> Tuple[bool, Dict]:
#     df_1h = fetch_1h_bars("SPY", period="30d")
#     df_4h = resample_to_4h(df_1h)
#     if df_4h.empty or len(df_4h) < 3:
#         return False, {"reason": "insufficient_spy_data"}
    
#     close = df_4h["close"]
#     ret_4h = (close.iloc[-2] / close.iloc[-3]) - 1.0
#     ro = ret_4h <= RISK_OFF_THRESHOLD
#     return ro, {
#         "spy_close": float(close.iloc[-2]),
#         "spy_ret_4h": float(ret_4h),
#         "threshold": RISK_OFF_THRESHOLD
#     }

def risk_off_from_df_1h(df_1h_spy: pd.DataFrame) -> Tuple[bool, Dict]:
    df_4h = resample_to_4h(df_1h_spy)
    if df_4h.empty or len(df_4h) < 4:
        return False, {"reason": "insufficient_spy_data"}
    close = df_4h["close"]
    ret_4h = (close.iloc[-2] / close.iloc[-3]) - 1.0
    ro = ret_4h <= RISK_OFF_THRESHOLD
    return ro, {"spy_close": float(close.iloc[-2]), "spy_ret_4h": float(ret_4h), "threshold": RISK_OFF_THRESHOLD}

def nyse_trading_dates_around(center: date, days: int) -> Tuple[date, date]:
    if HAS_MCAL:
        nyse = mcal.get_calendar("NYSE")
        start = center - timedelta(days=days * 3)
        end = center + timedelta(days=days * 3)
        sched = nyse.schedule(start_date=start, end_date=end)

        sessions = pd.to_datetime(sched.index.date)

        center64 = np.array([np.datetime64(center, "D")], dtype="datetime64[D]")
        idx = np.searchsorted(sessions.values.astype("datetime64[D]"), center64)[0]

        idx = min(max(idx, 0), len(sessions) - 1)
        left = max(idx - days, 0)
        right = min(idx + days, len(sessions) - 1)

        return sessions[left].date(), sessions[right].date()
    else:
        return center - timedelta(days=days), center + timedelta(days=days)

def finnhub_earnings_dates(symbol: str, from_d: date, to_d: date) -> List[date]:
    if not FINNHUB_KEY:
        return []
    url = "https://finnhub.io/api/v1/calendar/earnings"
    params = {
        "symbol": symbol,
        "from": from_d.strftime("%Y-%m-%d"),
        "to": to_d.strftime("%Y-%m-%d"),
        "token": FINNHUB_KEY,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    js = r.json() or {}
    items = js.get("earningsCalendar") or []
    out = []
    for it in items:
        d = it.get("date")
        if d:
            try:
                out.append(datetime.strptime(d, "%Y-%m-%d").date())
            except Exception:
                pass
    return sorted(list(set(out)))

def earnings_blocked(conn, symbol: str, days: int) -> Tuple[bool, Dict]:
    today_ny = datetime.now(timezone.utc).astimezone(NY_TZ).date() if NY_TZ else datetime.now(timezone.utc).date()
    win_from, win_to = nyse_trading_dates_around(today_ny, days)

    cur = conn.cursor()
    cur.execute("""
        SELECT earnings_date
        FROM earnings_cache
        WHERE symbol=? AND earnings_date BETWEEN ? AND ?
    """, (symbol, win_from.strftime("%Y-%m-%d"), win_to.strftime("%Y-%m-%d")))
    cached = [datetime.strptime(r[0], "%Y-%m-%d").date() for r in cur.fetchall()]

    if not cached:
        # 1) 이 window를 최근에 이미 조회했는지 확인
        cur.execute("""
            SELECT fetched_utc
            FROM earnings_window_fetch
            WHERE symbol=? AND win_from=? AND win_to=?
        """, (symbol, win_from.strftime("%Y-%m-%d"), win_to.strftime("%Y-%m-%d")))
        already = cur.fetchone()

        if not already:
            # 2) 이번 window는 처음(또는 DB에 기록 없음) → Finnhub 호출
            dates = finnhub_earnings_dates(symbol, win_from, win_to)
            fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

            # (a) 날짜가 있으면 cache에 저장
            for d in dates:
                cur.execute("""
                    INSERT OR IGNORE INTO earnings_cache(symbol, earnings_date, fetched_utc)
                    VALUES(?,?,?)
                """, (symbol, d.strftime("%Y-%m-%d"), fetched_utc))

            # (b) 날짜가 없어도 window fetch 기록은 저장 (재호출 방지)
            cur.execute("""
                INSERT OR REPLACE INTO earnings_window_fetch(symbol, win_from, win_to, fetched_utc)
                VALUES(?,?,?,?)
            """, (symbol, win_from.strftime("%Y-%m-%d"), win_to.strftime("%Y-%m-%d"), fetched_utc))

            # conn.commit()

            cached = dates
        else:
            # 이미 이번 window는 조회했는데 earnings가 없었던 케이스일 가능성
            cached = []
    
    if not cached:
        return False, {"window": (str(win_from), str(win_to)), "earnings_dates": []}
    
    return True, {"window": (str(win_from), str(win_to)), "earnings_dates": [str(d) for d in cached]}

@dataclass
class SignalInfo:
    ema_fast: float
    ema_slow: float
    rsi: Optional[float]
    reason: str

def make_signal_4h(df_4h: pd.DataFrame) -> Tuple[str, SignalInfo]:
    if df_4h.empty or len(df_4h) < 80:
        return "HOLD", SignalInfo(np.nan, np.nan, None, "not_enough_data")
    
    close = df_4h["close"]
    e20 = ema(close, 20)
    e60 = ema(close, 60)
    r = rsi(close, 14)

    e20_now, e60_now = float(e20.iloc[-1]), float(e60.iloc[-1])
    r_now = None if np.isnan(r.iloc[-1]) else float(r.iloc[-1])

    above_e20_two = (close.iloc[-1] > e20.iloc[-1]) and (close.iloc[-2] > e20.iloc[-2])
    trend_up = e20.iloc[-1] > e60.iloc[-1]
    trend_down = close.iloc[-1] < e60.iloc[-1]

    if trend_up and above_e20_two and (r_now is None or r_now < 70):
        return "BUY", SignalInfo(e20_now, e60_now, r_now, "EMA20>EMA60 & close>EMA20 for 2 bars & RSI<70")
    if trend_down or (r_now is not None and r_now > 75):
        return "SELL", SignalInfo(e20_now, e60_now, r_now, "close<EMA60 OR RSI>75")
    return "HOLD", SignalInfo(e20_now, e60_now, r_now, "no_trigger")


def score_buy(close: float, ema20: float, ema60: float, rsi_val: Optional[float]) -> float:
    """Rank BUY candidates for 4H trend-following.
    Higher is better.
      - trend strength: EMA20/EMA60
      - extension: close above EMA20 (small positive is OK)
      - RSI penalty: avoid overheated names
    """
    if ema20 is None or ema60 is None or ema20 <= 0 or ema60 <= 0:
        return -1e9
    trend = (ema20 / ema60 - 1.0) * 100.0
    extension = (close / ema20 - 1.0) * 100.0
    r = 50.0 if rsi_val is None else float(rsi_val)
    rsi_penalty = max(0.0, r - 60.0) * 0.7
    return trend * 2.0 + extension * 1.0 - rsi_penalty


def score_sell(close: float, ema60: float, rsi_val: Optional[float]) -> float:
    """Rank SELL candidates.
    Higher is better.
      - breakdown: how far close is below EMA60
      - RSI overheat: how far above 75
    """
    if ema60 is None or ema60 <= 0:
        return -1e9
    breakdown = max(0.0, (ema60 - close) / ema60) * 100.0
    r = 50.0 if rsi_val is None else float(rsi_val)
    overheat = max(0.0, r - 75.0)
    return breakdown * 2.0 + overheat * 1.0


def should_notify(prev_signal: str, new_signal: str) -> bool:
    if NOTIFY_HOLD:
        return new_signal != prev_signal
    return new_signal in ("BUY", "SELL") and new_signal != prev_signal

def format_msg(symbol: str,
               signal: str,
               last_close: float,
               info: SignalInfo,
               risk_off: bool,
               risk_meta: Dict,
               earnings_block: bool,
               earn_meta: Dict,
               note: str,
               score: Optional[float] = None) -> str:
    """Compact, readable Telegram message."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    rsi_str = "NA" if info.rsi is None else f"{info.rsi:.1f}"

    spy_ret = risk_meta.get("spy_ret_4h", None)
    spy_ret_str = f"{float(spy_ret):+.4f}" if isinstance(spy_ret, (float, int)) else "NA"
    thr = risk_meta.get("threshold", "NA")

    edates = earn_meta.get("earnings_dates", []) or []
    edates_str = ",".join(edates) if edates else "-"

    icon = "🟢" if signal == "BUY" else ("🔴" if signal == "SELL" else "⚪")
    score_line = f"Score: {score:.2f}\n" if score is not None else ""

    lines = [
        f"{icon} {symbol} | {signal}   ({now_utc} UTC)",
        score_line.rstrip(),
        f"Close: {last_close:.2f}   EMA20: {info.ema_fast:.2f}   EMA60: {info.ema_slow:.2f}   RSI: {rsi_str}",
        f"Why: {info.reason}",
        f"Filters: RiskOff={risk_off} (SPY4H {spy_ret_str}, thr={thr}) | EarningsBlock={earnings_block} (dates={edates_str})",
    ]
    if note:
        lines.append(f"Note: {note}")
    lines.append("Disclaimer: Not financial advice.")
    return "\n".join([x for x in lines if x])


def job():
    """
    Top-N (BUY/SELL) only + final summary (always).
    - Processes entire WATCHLIST (bulk 1h download + fallback)
    - Builds BUY/SELL candidate lists, ranks, sends Top-N
    - Sends one Run Summary at the end no matter what
    """
    if ONLY_REGULAR and not is_regular_market_hours_now():
        return

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    # Always have safe defaults so summary can be built even if something fails early
    ro = False
    ro_meta = {"spy_ret_4h": None, "threshold": RISK_OFF_THRESHOLD}

    buy_candidates: List[Tuple[float, str, str]] = []
    sell_candidates: List[Tuple[float, str, str]] = []
    hold_symbols: List[str] = []
    blocked_risk = 0
    blocked_earnings = 0

    processed = 0
    evaluated = 0
    skipped_data = 0
    errors = 0
    sent = 0

    # (Optional) collect a few recent error strings for summary
    error_samples: List[str] = []

    conn = db_connect()
    try:
        # Bulk download (fast path). Fallback per ticker when needed.
        multi_df = None
        try:
            symbols = list(set(WATCHLIST + ["SPY"]))
            multi_df = yf.download(
                tickers=" ".join(symbols),
                period="60d",
                interval="1h",
                group_by="column",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            if multi_df is not None and not multi_df.empty:
                if multi_df.index.tz is None:
                    multi_df.index = multi_df.index.tz_localize("America/New_York")
                multi_df.index = multi_df.index.tz_convert("UTC")
        except Exception:
            multi_df = None

        def get_1h_df_for(sym: str) -> pd.DataFrame:
            if (
                multi_df is not None
                and not multi_df.empty
                and isinstance(multi_df.columns, pd.MultiIndex)
            ):
                cols = []
                for k in ["Open", "High", "Low", "Close", "Volume"]:
                    if (k, sym) in multi_df.columns:
                        cols.append((k, sym))
                if len(cols) == 5:
                    df = multi_df[cols].copy()
                    df.columns = ["open", "high", "low", "close", "volume"]
                    return df.dropna()
            return fetch_1h_bars(sym, period="60d")

        # Market regime (SPY 4H)
        try:
            df_spy_1h = get_1h_df_for("SPY")
            if df_spy_1h.empty:
                df_spy_1h = fetch_1h_bars("SPY", period="60d")
            ro, ro_meta = risk_off_from_df_1h(df_spy_1h)
        except Exception as e:
            # If SPY fails, do not block trading, but record error
            errors += 1
            error_samples.append(f"SPY:{type(e).__name__}:{e}")
            ro = False
            ro_meta = {"spy_ret_4h": None, "threshold": RISK_OFF_THRESHOLD}

        for i, sym in enumerate(WATCHLIST, 1):
            processed += 1
            pos = get_position(conn, sym)

            try:
                # Earnings filter
                eblock, e_meta = earnings_blocked(conn, sym, EARNINGS_FILTER_DAYS)

                # Data
                df_1h = get_1h_df_for(sym)
                df_4h = resample_to_4h(df_1h)

                # Need enough 4H bars for EMA60/RSI14 stability
                if df_4h.empty or len(df_4h) < 80:
                    skipped_data += 1
                    continue

                evaluated += 1
                signal, info = make_signal_4h(df_4h)
                last_close = float(df_4h["close"].iloc[-1])

                filtered_signal = signal
                note = ""

                # Filters (apply only to BUY by default)
                if ro and signal == "BUY":
                    filtered_signal = "HOLD"
                    note = f"blocked_by_risk_off (SPY 4H <= {RISK_OFF_THRESHOLD})"
                    blocked_risk += 1

                if eblock and signal == "BUY":
                    filtered_signal = "HOLD"
                    note = f"blocked_by_earnings_window (±{EARNINGS_FILTER_DAYS}d)"
                    blocked_earnings += 1

                # Log for this run_ts (groupable)
                conn.execute(
                    """
                    INSERT INTO signal_log(utc_time,symbol,signal,close,ema_fast,ema_slow,rsi,risk_off,earnings_block,note)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        run_ts,
                        sym,
                        filtered_signal,
                        last_close,
                        None if np.isnan(info.ema_fast) else float(info.ema_fast),
                        None if np.isnan(info.ema_slow) else float(info.ema_slow),
                        None if info.rsi is None else float(info.rsi),
                        1 if ro else 0,
                        1 if eblock else 0,
                        note,
                    ),
                )

                prev_sig = pos["last_signal"]
                notify = should_notify(prev_sig, filtered_signal)

                # Collect for Top-N sending
                if notify:
                    if filtered_signal == "BUY":
                        sc = score_buy(last_close, info.ema_fast, info.ema_slow, info.rsi)
                        msg = format_msg(
                            sym, filtered_signal, last_close, info,
                            ro, ro_meta, eblock, e_meta, note, score=sc
                        )
                        buy_candidates.append((sc, sym, msg))
                        pos["last_notified_utc"] = run_ts

                    elif filtered_signal == "SELL":
                        sc = score_sell(last_close, info.ema_slow, info.rsi)
                        msg = format_msg(
                            sym, filtered_signal, last_close, info,
                            ro, ro_meta, eblock, e_meta, note, score=sc
                        )
                        sell_candidates.append((sc, sym, msg))
                        pos["last_notified_utc"] = run_ts

                    else:
                        hold_symbols.append(sym)

                pos["last_signal"] = filtered_signal
                pos["updated_utc"] = run_ts
                upsert_position(conn, pos)

                if i % 25 == 0:
                    conn.commit()

                time.sleep(0.02)

            except Exception as e:
                errors += 1
                # keep error samples (avoid spam). If you want per-symbol error messages, uncomment tg_send.
                if len(error_samples) < 10:
                    error_samples.append(f"{sym}:{type(e).__name__}:{e}")
                # tg_send(f"[{run_ts} UTC] {sym} error: {type(e).__name__}: {e}")
                continue

        # Rank
        buy_candidates.sort(key=lambda x: x[0], reverse=True)
        sell_candidates.sort(key=lambda x: x[0], reverse=True)

        # Extra safety: if risk-off, suppress BUY notifications
        if ro:
            buy_candidates = []

        top_buy = buy_candidates[:max(0, TOP_N_BUY)]
        top_sell = sell_candidates[:max(0, TOP_N_SELL)]

        # Send Top-N
        for _, _, msg in top_buy:
            ok = tg_send(msg)
            if ok is not False:
                sent += 1
            time.sleep(0.4)

        if SEND_SELL:
            for _, _, msg in top_sell:
                ok = tg_send(msg)
                if ok is not False:
                    sent += 1
                time.sleep(0.4)

        conn.commit()

    finally:
        # Always send summary even if exceptions happened
        try:
            spy_ret = ro_meta.get("spy_ret_4h", None)
            spy_ret_str = f"{float(spy_ret):+.4f}" if isinstance(spy_ret, (float, int)) else "NA"

            tb_syms = ",".join([s for _, s, _ in buy_candidates[:max(0, TOP_N_BUY)]]) if buy_candidates else "-"
            ts_syms = ",".join([s for _, s, _ in sell_candidates[:max(0, TOP_N_SELL)]]) if sell_candidates else "-"

            hold_line = ""
            if SEND_HOLD_SUMMARY:
                hold_line = (
                    f"\nHOLD(notified): {len(hold_symbols)}"
                    + (
                        f" sample={','.join(hold_symbols[:10])}{'...' if len(hold_symbols) > 10 else ''}"
                        if hold_symbols
                        else ""
                    )
                )

            err_line = ""
            if error_samples:
                err_line = "\nERR(sample): " + " | ".join(error_samples[:5])

            summary = (
                f"📌 Run Summary ({run_ts} UTC)\n"
                f"Watchlist={len(WATCHLIST)} | Processed={processed} | Evaluated={evaluated} | "
                f"Skipped(data)={skipped_data} | Errors={errors} | Sent={sent}\n"
                f"RiskOff={ro} (SPY4H {spy_ret_str}, thr={RISK_OFF_THRESHOLD}) | "
                f"EarningsBlocked(BUY)={blocked_earnings} | RiskBlocked(BUY)={blocked_risk}\n"
                f"Top BUY({TOP_N_BUY}): {tb_syms}\n"
                f"Top SELL({TOP_N_SELL}): {ts_syms}"
                f"{hold_line}{err_line}\n"
                f"Disclaimer: Not financial advice."
            )
            tg_send(summary)
        except Exception as e:
            # Don't crash scheduler on summary failure
            print("[job] summary send failed:", type(e).__name__, e)

        try:
            conn.close()
        except Exception:
            pass


def main():
    db_init()
    tg_send("Signal bot started (4H, yfinance). Filters: earnings(±N days) + SPY risk-off. Not financial advice.")
    # job()
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job, "interval", hours=RUN_EVERY_HOURS, next_run_time=datetime.now(timezone.utc))
    sched.start()

if __name__ == "__main__":
    main()

# sqlite3 signals.db "delete from positions;"