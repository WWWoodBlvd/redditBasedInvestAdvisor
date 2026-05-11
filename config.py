SUBREDDITS = [
    # ── Stocks ──────────────────────────────────────────────────────────────
    {"name": "Stocks_Picks",       "category": "Stocks",  "subscribers": 77919,   "enabled": True},
    {"name": "wallstreetbets",     "category": "Stocks",  "subscribers": 13500000, "enabled": True},
    {"name": "stocks",             "category": "Stocks",  "subscribers": 9000000,  "enabled": True},
    {"name": "investing",          "category": "Stocks",  "subscribers": 3000000,  "enabled": True},
    {"name": "StockMarket",        "category": "Stocks",  "subscribers": 818000,   "enabled": True},
    {"name": "pennystocks",        "category": "Stocks",  "subscribers": 1800000,  "enabled": True},
    {"name": "SecurityAnalysis",   "category": "Stocks",  "subscribers": 125000,   "enabled": True},
    {"name": "ValueInvesting",     "category": "Stocks",  "subscribers": 39000,    "enabled": True},
    {"name": "dividends",          "category": "Stocks",  "subscribers": 521000,   "enabled": True},
    {"name": "UndervaluedStonks",  "category": "Stocks",  "subscribers": 14000,    "enabled": True},
    {"name": "EducatedInvesting",  "category": "Stocks",  "subscribers": 15000,    "enabled": True},
    {"name": "InvestmentClub",     "category": "Stocks",  "subscribers": 52000,    "enabled": True},
    {"name": "SPACs",              "category": "Stocks",  "subscribers": 87000,    "enabled": True},
    {"name": "weedstocks",         "category": "Stocks",  "subscribers": 162000,   "enabled": True},
    {"name": "IndianStockMarket",  "category": "Stocks",  "subscribers": 1200000,  "enabled": True},

    # ── Options ─────────────────────────────────────────────────────────────
    {"name": "options",            "category": "Options", "subscribers": 816000,   "enabled": True},
    {"name": "smallstreetbets",    "category": "Options", "subscribers": 152000,   "enabled": True},

    # ── Crypto ──────────────────────────────────────────────────────────────
    {"name": "CryptoCurrency",     "category": "Crypto",  "subscribers": 5000000,  "enabled": True},
    {"name": "CryptoMoonShots",    "category": "Crypto",  "subscribers": 2000000,  "enabled": True},
    {"name": "Bitcoin",            "category": "Crypto",  "subscribers": 6000000,  "enabled": True},
    {"name": "Ethereum",           "category": "Crypto",  "subscribers": 1500000,  "enabled": True},
    {"name": "ethtrader",          "category": "Crypto",  "subscribers": 1700000,  "enabled": True},
]

CATEGORIES = ["Stocks", "Options", "Crypto"]

# Common English words that look like tickers — excluded from detection
TICKER_BLACKLIST = {
    # Single letters
    "A", "I",
    # Common 2-letter non-tickers
    "AI", "IT", "EV", "AR", "VR", "ML", "UI", "VC", "BC", "AD", "RE",
    "AM", "AN", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN",
    "IS", "ME", "MY", "NO", "OF", "OK", "ON", "OR", "SO", "TO", "UP",
    "US", "WE", "PE", "PM", "PR", "DD", "TA",
    # Common 3-letter non-tickers
    "ALL", "AND", "ARE", "BUT", "CAN", "DAY", "DID", "FOR",
    "GET", "GOT", "HAD", "HAS", "HER", "HIM", "HIS", "HOW", "ITS", "LET",
    "MAY", "NEW", "NOT", "NOW", "OFF", "OLD", "ONE", "OUR", "OUT", "OWN",
    "SAY", "SHE", "THE", "TOO", "TWO", "USE", "WAS", "WAY", "WHO",
    "WHY", "YOU", "ANY", "CEO", "CFO", "COO", "IPO", "ETF", "ATH", "ATL",
    "DCA", "EPS", "GDP", "IMO", "LOL", "OTC", "PUT",
    # Common 4-letter non-tickers
    "EDIT", "TLDR", "YOLO", "FOMO", "HODL", "MOON", "BEAR", "BULL",
    "CALL", "SELL", "HOLD", "LOSS", "GAIN", "HIGH", "LOW",
    "CASH", "DEBT", "FUND", "GOLD", "SAFE", "RISK", "RATE", "BANK",
    "LONG", "STOP", "OPEN", "THAT", "THIS", "WITH", "YOUR",
    "HAVE", "FROM", "THEY", "BEEN", "WILL", "WHEN", "MORE", "ALSO",
    "INTO", "THAN", "THEN", "SOME", "WHAT", "OVER", "JUST", "LIKE",
    "TIME", "YEAR", "WEEK", "DAYS", "GOOD", "MADE", "MAKE", "MUCH",
    "NEXT", "LAST", "EACH", "DOES", "WERE", "SAID", "WELL", "BOTH",
    "ONLY", "VERY", "EVEN", "BACK", "AFTER", "TAKE", "WANT", "LOOK",
    "DONT", "CANT", "WONT", "ISNT", "NEWS", "POST", "PRICE", "STOCK",
    "APES", "LINK", "FEDS", "DUMP", "PUMP", "REKT", "DIPS", "PUTS",
    "LOSS", "LMAO", "LMFAO", "ROFL", "IMHO", "AFAIK", "ASAP",
    "EBITDA", "CAPEX", "OPEX", "SAAS", "PAAS",
}
