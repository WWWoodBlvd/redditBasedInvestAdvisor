# Reddit-Based Investment Advisor

A Streamlit app that scans investment-related subreddits, identifies the most-mentioned stocks and crypto, scores them by sentiment and engagement, and displays performance metrics over 1D/1W/1M/6M/YTD/12M periods.

**Not financial advice.**

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## Features

- Scans 17+ investing subreddits via Reddit's public JSON (no API keys needed)
- 4-tier ticker detection: `$TICKER`, context-aware (e.g. "DRAM ETF"), bare uppercase, known-ticker map
- Sentiment scoring (bullish/bearish lexicon, 60+ keywords)
- Upvote-weighted engagement
- Live price performance via Yahoo Finance (batch fetch)
- Categorized tabs: All / Stocks / Options / Crypto
- Configurable: days, min mentions, scan depth, top N, min subscribers, categories
- 5-minute result cache + per-ticker price cache
