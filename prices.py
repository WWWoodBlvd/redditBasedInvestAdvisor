"""
Batch price-performance fetcher.
Uses yfinance batch download — fetches all tickers in a single API call.
"""

import warnings
import yfinance as yf
import pandas as pd
from datetime import date

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from detector import CRYPTO_MAP

PERIODS = ["1D", "1W", "1M", "6M", "YTD", "12M"]
_PERIOD_DAYS = {"1D": 1, "1W": 5, "1M": 21, "6M": 126, "12M": 252}
_CRYPTO_TICKERS = set(CRYPTO_MAP.keys())


def _yf_symbol(ticker: str) -> str:
    return f"{ticker}-USD" if ticker in _CRYPTO_TICKERS else ticker


def _empty():
    return {p: {"pct": None, "dollar": None} for p in PERIODS}


def fetch_performance(tickers: list) -> dict:
    """
    Single-batch yfinance call for all tickers. Much faster than per-ticker.
    Returns {ticker: {price, 1D, 1W, 1M, 6M, YTD, 12M}}.
    """
    if not tickers:
        return {}

    symbol_to_ticker = {_yf_symbol(t): t for t in tickers}
    symbols = list(symbol_to_ticker.keys())

    try:
        data = yf.download(
            tickers=symbols,
            period="1y",
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return {t: {"price": None, **_empty()} for t in tickers}

    results = {}
    today_year = date.today().year

    for symbol, ticker in symbol_to_ticker.items():
        try:
            # When there's only one ticker, yf returns a flat DataFrame
            if len(symbols) == 1:
                closes = data["Close"]
            else:
                closes = data[symbol]["Close"]

            closes = closes.dropna()
            if len(closes) < 2:
                results[ticker] = {"price": None, **_empty()}
                continue

            current = float(closes.iloc[-1])
            row = {"price": round(current, 2)}

            # Standard day-offset periods
            for period, days_back in _PERIOD_DAYS.items():
                if len(closes) > days_back:
                    past = float(closes.iloc[-(days_back + 1)])
                    dollar = current - past
                    pct = (dollar / past) * 100 if past else 0
                    row[period] = {"pct": round(pct, 2), "dollar": round(dollar, 2)}
                else:
                    row[period] = {"pct": None, "dollar": None}

            # YTD — find first trading day of current year
            ytd_mask = closes.index.year == today_year
            if ytd_mask.any():
                ytd_start = float(closes[ytd_mask].iloc[0])
                dollar = current - ytd_start
                pct = (dollar / ytd_start) * 100 if ytd_start else 0
                row["YTD"] = {"pct": round(pct, 2), "dollar": round(dollar, 2)}
            else:
                row["YTD"] = {"pct": None, "dollar": None}

            results[ticker] = row

        except Exception:
            results[ticker] = {"price": None, **_empty()}

    # Anything we missed
    for t in tickers:
        if t not in results:
            results[t] = {"price": None, **_empty()}

    return results
