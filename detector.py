"""
Stock & crypto mention detector.
Detects both ticker symbols ($AAPL, TSLA) and company/coin names (Apple, Tesla).
"""

import re
from collections import defaultdict
from config import TICKER_BLACKLIST

# ── Known tickers + company name aliases ────────────────────────────────────
STOCK_MAP: dict[str, list[str]] = {
    # Mega cap
    "AAPL":  ["Apple"],
    "MSFT":  ["Microsoft"],
    "GOOGL": ["Google", "Alphabet"],
    "GOOG":  ["Google", "Alphabet"],
    "AMZN":  ["Amazon"],
    "NVDA":  ["Nvidia", "NVIDIA"],
    "META":  ["Meta", "Facebook"],
    "TSLA":  ["Tesla"],
    "BRK.B": ["Berkshire"],
    "JPM":   ["JPMorgan", "JP Morgan"],
    "V":     ["Visa"],
    "MA":    ["Mastercard"],
    "UNH":   ["UnitedHealth"],
    "XOM":   ["Exxon"],
    "WMT":   ["Walmart"],
    "LLY":   ["Eli Lilly"],
    "JNJ":   ["Johnson"],
    "PG":    ["Procter", "P&G"],
    "HD":    ["Home Depot"],
    "CVX":   ["Chevron"],
    # Tech
    "AMD":   ["AMD", "Advanced Micro"],
    "INTC":  ["Intel"],
    "QCOM":  ["Qualcomm"],
    "CRM":   ["Salesforce"],
    "ORCL":  ["Oracle"],
    "ADBE":  ["Adobe"],
    "NOW":   ["ServiceNow"],
    "PLTR":  ["Palantir"],
    "SNOW":  ["Snowflake"],
    "NET":   ["Cloudflare"],
    "DDOG":  ["Datadog"],
    "CRWD":  ["CrowdStrike"],
    "ZS":    ["Zscaler"],
    "UBER":  ["Uber"],
    "LYFT":  ["Lyft"],
    "ABNB":  ["Airbnb"],
    "SHOP":  ["Shopify"],
    "SQ":    ["Block", "Square"],
    "PYPL":  ["PayPal"],
    "COIN":  ["Coinbase"],
    "RBLX":  ["Roblox"],
    "SNAP":  ["Snapchat", "Snap"],
    "PINS":  ["Pinterest"],
    "SPOT":  ["Spotify"],
    "NFLX":  ["Netflix"],
    "DIS":   ["Disney"],
    "ROKU":  ["Roku"],
    "TWLO":  ["Twilio"],
    "HOOD":  ["Robinhood"],
    "SOFI":  ["SoFi"],
    "AFRM":  ["Affirm"],
    "UPST":  ["Upstart"],
    # EV / Energy
    "RIVN":  ["Rivian"],
    "LCID":  ["Lucid"],
    "NIO":   ["NIO"],
    "XPEV":  ["XPeng"],
    "LI":    ["Li Auto"],
    "ENPH":  ["Enphase"],
    "FSLR":  ["First Solar"],
    "PLUG":  ["Plug Power"],
    # Finance / Banks
    "BAC":   ["Bank of America"],
    "GS":    ["Goldman Sachs", "Goldman"],
    "MS":    ["Morgan Stanley"],
    "WFC":   ["Wells Fargo"],
    "C":     ["Citigroup", "Citi"],
    "BX":    ["Blackstone"],
    "KKR":   ["KKR"],
    # Healthcare / Biotech
    "PFE":   ["Pfizer"],
    "MRNA":  ["Moderna"],
    "BNTX":  ["BioNTech"],
    "ABBV":  ["AbbVie"],
    "BMY":   ["Bristol Myers"],
    "GILD":  ["Gilead"],
    "REGN":  ["Regeneron"],
    "VRTX":  ["Vertex"],
    "ISRG":  ["Intuitive Surgical"],
    # ETFs
    "SPY":   ["S&P 500 ETF", "SPY"],
    "QQQ":   ["Nasdaq ETF", "QQQ"],
    "IWM":   ["Russell 2000"],
    "DIA":   ["Dow Jones ETF"],
    "VTI":   ["Vanguard Total"],
    "VOO":   ["Vanguard S&P"],
    "ARKK":  ["ARK Innovation", "Cathie Wood"],
    # Meme / Popular
    "GME":   ["GameStop", "Game Stop"],
    "AMC":   ["AMC"],
    "BB":    ["BlackBerry"],
    "BBBY":  ["Bed Bath"],
    "SPCE":  ["Virgin Galactic"],
    "MSTR":  ["MicroStrategy"],
    # Cannabis
    "TLRY":  ["Tilray"],
    "CGC":   ["Canopy Growth"],
    "ACB":   ["Aurora Cannabis"],
}

CRYPTO_MAP: dict[str, list[str]] = {
    "BTC":  ["Bitcoin"],
    "ETH":  ["Ethereum"],
    "SOL":  ["Solana"],
    "XRP":  ["Ripple"],
    "ADA":  ["Cardano"],
    "DOGE": ["Dogecoin"],
    "SHIB": ["Shiba"],
    "AVAX": ["Avalanche"],
    "DOT":  ["Polkadot"],
    "MATIC":["Polygon"],
    "LINK": ["Chainlink"],
    "UNI":  ["Uniswap"],
    "LTC":  ["Litecoin"],
    "BCH":  ["Bitcoin Cash"],
    "ATOM": ["Cosmos"],
    "FIL":  ["Filecoin"],
    "APT":  ["Aptos"],
    "ARB":  ["Arbitrum"],
    "OP":   ["Optimism"],
    "INJ":  ["Injective"],
    "SUI":  ["SUI"],
    "SEI":  ["SEI"],
}

# Build reverse lookup: lowercase alias → canonical ticker
_ALIAS_TO_TICKER: dict[str, str] = {}

def _build_alias_map():
    for ticker, aliases in {**STOCK_MAP, **CRYPTO_MAP}.items():
        for alias in aliases:
            _ALIAS_TO_TICKER[alias.lower()] = ticker

_build_alias_map()

# Tier 1: $TICKER — always count
_DOLLAR_RE = re.compile(r'\$([A-Z]{1,5})')

# Tier 2: bare 4-5 char uppercase — open-ended, catches unknowns
_BARE_LONG_RE = re.compile(r'(?<![A-Za-z$])([A-Z]{4,5})(?![a-z])')

# Tier 3: bare 2-3 char uppercase — only if in known maps
_BARE_SHORT_RE = re.compile(r'(?<![A-Za-z$])([A-Z]{2,3})(?![a-z])')

# Tier 0: financial context pattern — word adjacent to "ETF", "stock", "shares",
# "calls", "puts", "options", "ticker", "position", "shares" etc. is always a ticker
_FINANCIAL_CONTEXT_WORDS = r'(?:etf|stock|stocks|shares|calls?|puts?|options?|ticker|position|warrant|leaps?|futures?)'
_CONTEXT_BEFORE_RE = re.compile(
    rf'(?<![A-Za-z$])([A-Z]{{1,5}})\s+{_FINANCIAL_CONTEXT_WORDS}',
    re.IGNORECASE,
)
_CONTEXT_AFTER_RE = re.compile(
    rf'{_FINANCIAL_CONTEXT_WORDS}\s+([A-Z]{{1,5}})(?![a-z])',
    re.IGNORECASE,
)

_KNOWN_TICKERS = set(STOCK_MAP.keys()) | set(CRYPTO_MAP.keys())


def detect_mentions(text: str) -> list[str]:
    """
    4-tier ticker detection:
      Tier 0: TICKER + financial context word (e.g. "DRAM ETF", "NVDA calls") → always count
      Tier 1: $TICKER → always count
      Tier 2: bare 4-5 char uppercase → count if not blacklisted
      Tier 3: bare 2-3 char uppercase → only if in known maps
    Plus company/coin name alias matching.
    """
    found = set()

    # Tier 0 — financial context: strongest signal for ambiguous tickers
    for m in _CONTEXT_BEFORE_RE.finditer(text):
        t = m.group(1).upper()
        if t not in TICKER_BLACKLIST:
            found.add(t)
    for m in _CONTEXT_AFTER_RE.finditer(text):
        t = m.group(1).upper()
        if t not in TICKER_BLACKLIST:
            found.add(t)

    # Tier 1 — dollar-prefixed
    for m in _DOLLAR_RE.finditer(text):
        t = m.group(1)
        if t not in TICKER_BLACKLIST:
            found.add(t)

    # Tier 2 — bare 4-5 char uppercase
    for m in _BARE_LONG_RE.finditer(text):
        t = m.group(1)
        if t not in TICKER_BLACKLIST:
            found.add(t)

    # Tier 3 — bare 2-3 char uppercase, known tickers only
    for m in _BARE_SHORT_RE.finditer(text):
        t = m.group(1)
        if t not in TICKER_BLACKLIST and t in _KNOWN_TICKERS:
            found.add(t)

    # Company / coin name aliases
    text_lower = text.lower()
    for alias, ticker in _ALIAS_TO_TICKER.items():
        if alias in text_lower:
            found.add(ticker)

    return list(found)


# ── Sentiment lexicon ────────────────────────────────────────────────────────
_BULLISH_WORDS = {
    "buy", "buying", "bought", "long", "calls", "moon", "rocket", "bullish",
    "pump", "rally", "rip", "ripping", "breakout", "squeeze", "tendies",
    "hold", "holding", "diamond", "hodl", "yolo", "gains", "winner",
    "up", "rising", "soar", "soaring", "beat", "beats", "earnings beat",
    "undervalued", "cheap", "discount", "outperform", "strong",
    "love", "great", "amazing", "best", "winning", "🚀", "🌙", "🟢", "💎", "🙌",
}
_BEARISH_WORDS = {
    "sell", "selling", "sold", "short", "puts", "dump", "dumping", "crash",
    "bearish", "bear", "rip off", "bagholder", "bag", "loss", "losses",
    "down", "falling", "drop", "dropping", "tank", "tanking", "puke",
    "overvalued", "expensive", "underperform", "weak", "decline",
    "hate", "terrible", "worst", "avoid", "garbage", "trash",
    "🔴", "📉", "💀", "🐻",
}
_VERY_BULLISH = {"calls", "long", "buy", "buying", "bullish", "🚀", "moon", "rocket"}
_VERY_BEARISH = {"puts", "short", "sell", "selling", "bearish", "crash", "📉"}


def _sentiment_score(text: str) -> int:
    """
    Returns -3..+3 sentiment score for a piece of text.
    Negative = bearish, Positive = bullish.
    """
    text_l = text.lower()
    bull = sum(1 for w in _BULLISH_WORDS if w in text_l)
    bear = sum(1 for w in _BEARISH_WORDS if w in text_l)
    very_bull = sum(1 for w in _VERY_BULLISH if w in text_l)
    very_bear = sum(1 for w in _VERY_BEARISH if w in text_l)
    # Weight strong signals more heavily
    return (bull + 2 * very_bull) - (bear + 2 * very_bear)


def aggregate_mentions(
    text_items: list[dict],
    min_mentions: int = 1,
) -> dict[str, dict]:
    """
    Aggregates ticker mentions with sentiment and engagement weighting.

    Each item: {subreddit, text, created_utc, [post_id], [score]}

    Returns per ticker:
      {
        count:       int      # raw mention count
        unique_posts: int     # distinct posts mentioning ticker
        subreddits:  set[str]
        samples:     list[str]
        is_crypto:   bool
        sentiment:   int      # cumulative bullish-bearish score
        bullish:     int      # # of bullish mentions
        bearish:     int      # # of bearish mentions
        engagement:  int      # sum of upvotes across mentioning posts
      }
    """
    counts: dict[str, dict] = defaultdict(lambda: {
        "count":        0,
        "unique_posts": set(),
        "subreddits":   set(),
        "samples":      [],
        "is_crypto":    False,
        "sentiment":    0,
        "bullish":      0,
        "bearish":      0,
        "engagement":   0,
    })

    for item in text_items:
        tickers = detect_mentions(item["text"])
        if not tickers:
            continue

        sent = _sentiment_score(item["text"])
        post_id = item.get("post_id") or item.get("text", "")[:50]
        score   = max(0, item.get("score", 0))

        for ticker in tickers:
            c = counts[ticker]
            c["count"] += 1
            c["unique_posts"].add(post_id)
            c["subreddits"].add(item["subreddit"])
            c["is_crypto"] = ticker in CRYPTO_MAP
            c["sentiment"] += sent
            c["engagement"] += score
            if sent > 0:
                c["bullish"] += 1
            elif sent < 0:
                c["bearish"] += 1

            if len(c["samples"]) < 5:
                snippet = item["text"][:240].replace("\n", " ").strip()
                c["samples"].append({
                    "text": snippet,
                    "subreddit": item["subreddit"],
                    "sentiment": sent,
                })

    # Finalize — convert unique_posts to int
    result = {}
    for t, v in counts.items():
        if v["count"] < min_mentions:
            continue
        v["unique_posts"] = len(v["unique_posts"])
        result[t] = v

    return result
