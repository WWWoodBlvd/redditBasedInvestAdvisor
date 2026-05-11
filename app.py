"""
Reddit-Based Investment Advisor — Streamlit UI
"""

import time
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime
from typing import Optional

from config import SUBREDDITS, CATEGORIES
from scanner import scan_all, SCAN_LIMITS, configure_oauth, auth_mode
from detector import aggregate_mentions, STOCK_MAP, CRYPTO_MAP
from prices import fetch_performance, PERIODS

st.set_page_config(
    page_title="Reddit Investment Advisor",
    page_icon="📈",
    layout="wide",
)

# Pull OAuth credentials from Streamlit secrets if configured
try:
    configure_oauth(
        st.secrets.get("REDDIT_CLIENT_ID", ""),
        st.secrets.get("REDDIT_CLIENT_SECRET", ""),
    )
except Exception:
    pass   # secrets not configured — fall back to public JSON

# ── Session state ────────────────────────────────────────────────────────────
DEFAULTS = {
    "subreddits":     lambda: [s.copy() for s in SUBREDDITS],
    "results":        lambda: None,
    "scan_time":      lambda: None,
    "scan_duration":  lambda: None,
    "cache":          lambda: {},
    "perf_cache":     lambda: {},
}
for k, factory in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = factory()

CACHE_TTL = 300


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_company_name(ticker: str) -> str:
    if ticker in STOCK_MAP and STOCK_MAP[ticker]:
        return STOCK_MAP[ticker][0]
    if ticker in CRYPTO_MAP and CRYPTO_MAP[ticker]:
        return CRYPTO_MAP[ticker][0]
    return "—"


def sentiment_label(score: int, bullish: int, bearish: int) -> str:
    """Visual sentiment marker for the table."""
    total = bullish + bearish
    if total == 0:
        return "⚪ Neutral"
    if score >= 5 and bullish > 2 * bearish:
        return "🟢🟢 Very Bullish"
    if score >= 2:
        return "🟢 Bullish"
    if score <= -5 and bearish > 2 * bullish:
        return "🔴🔴 Very Bearish"
    if score <= -2:
        return "🔴 Bearish"
    return "⚪ Mixed"


def results_to_df(results: dict, category_filter: Optional[str] = None) -> pd.DataFrame:
    option_subs = {s["name"] for s in st.session_state.subreddits if s["category"] == "Options"}
    rows = []
    for ticker, d in results.items():
        if category_filter == "Crypto" and not d["is_crypto"]:
            continue
        if category_filter == "Stocks" and d["is_crypto"]:
            continue
        if category_filter == "Options" and not d["subreddits"].intersection(option_subs):
            continue

        rows.append({
            "Ticker":       ticker,
            "Company":      get_company_name(ticker),
            "Mentions":     d["count"],
            "Posts":        d["unique_posts"],
            "Sentiment":    sentiment_label(d["sentiment"], d["bullish"], d["bearish"]),
            "_sent_score":  d["sentiment"],
            "Engagement":   d["engagement"],
            "Subreddits":   ", ".join(sorted(d["subreddits"])),
            "# Subs":       len(d["subreddits"]),
            "_samples":     d["samples"],
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Mentions", "Engagement"], ascending=[False, False]).reset_index(drop=True)
        df.index += 1
    return df


# ── Performance table rendering ──────────────────────────────────────────────
def _fmt_period(pct, dollar):
    if pct is None:
        return "—"
    sign = "+" if pct >= 0 else ""
    dsign = "+" if dollar >= 0 else "-"
    return f"{sign}{pct:.2f}%  ({dsign}${abs(dollar):,.2f})"


def _color_cell(val):
    if val == "—" or not isinstance(val, str):
        return "color: #888"
    if val.startswith("+"):
        return "color: #00c853; font-weight:600"
    if val.startswith("-"):
        return "color: #ff5252; font-weight:600"
    return ""


def render_results_tab(df: pd.DataFrame, label: str, top_n: int):
    if df.empty:
        st.info(f"No tickers found for {label} with current filters.")
        return

    top_df = df.head(top_n).copy()

    # ── Summary metrics ──
    c1, c2, c3, c4 = st.columns(4)
    top_pick = top_df.iloc[0]
    c1.metric("🏆 Top Pick", top_pick["Ticker"], f"{top_pick['Mentions']} mentions")

    bullish_df = top_df[top_df["_sent_score"] > 0]
    if not bullish_df.empty:
        most_bull = bullish_df.iloc[bullish_df["_sent_score"].argmax()]
        c2.metric("🟢 Most Bullish", most_bull["Ticker"], f"+{most_bull['_sent_score']} score")
    else:
        c2.metric("🟢 Most Bullish", "—")

    bearish_df = top_df[top_df["_sent_score"] < 0]
    if not bearish_df.empty:
        most_bear = bearish_df.iloc[bearish_df["_sent_score"].argmin()]
        c3.metric("🔴 Most Bearish", most_bear["Ticker"], f"{most_bear['_sent_score']} score")
    else:
        c3.metric("🔴 Most Bearish", "—")

    c4.metric("📊 Unique Tickers", len(df), f"showing top {top_n}")

    st.divider()

    # ── Bar chart ──
    fig = px.bar(
        top_df, x="Ticker", y="Mentions",
        color="_sent_score",
        color_continuous_scale=[(0, "#ff5252"), (0.5, "#888"), (1, "#00c853")],
        color_continuous_midpoint=0,
        text="Mentions",
        hover_data={"Company": True, "Posts": True, "Engagement": True, "_sent_score": False},
        title=f"Top {top_n} Most Mentioned — {label}  (green = bullish, red = bearish)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(coloraxis_showscale=False, height=380, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📈 Performance & Sentiment")

    # ── Fetch prices ──
    tickers = top_df["Ticker"].tolist()
    missing = [t for t in tickers if t not in st.session_state.perf_cache]
    if missing:
        with st.spinner(f"Fetching prices for {len(missing)} tickers (batch call)…"):
            fresh = fetch_performance(missing)
            st.session_state.perf_cache.update(fresh)
    perf = st.session_state.perf_cache

    # ── Build the display table ──
    rows = []
    export_rows = []
    for _, r in top_df.iterrows():
        t = r["Ticker"]
        p = perf.get(t, {})
        price = p.get("price")
        price_str = f"${price:,.2f}" if price else "—"

        disp = {
            "Ticker":     t,
            "Company":    r["Company"],
            "Mentions":   r["Mentions"],
            "Posts":      r["Posts"],
            "Sentiment":  r["Sentiment"],
            "Price":      price_str,
        }
        export = {
            "Ticker": t, "Company": r["Company"], "Mentions": r["Mentions"],
            "Posts": r["Posts"], "Sentiment": r["Sentiment"],
            "Engagement": r["Engagement"], "Price": price or "",
            "Subreddits": r["Subreddits"],
        }
        for period in PERIODS:
            pd_data = p.get(period, {})
            pct = pd_data.get("pct")
            dollar = pd_data.get("dollar")
            disp[period] = _fmt_period(pct, dollar)
            export[f"{period} %"] = pct if pct is not None else ""
            export[f"{period} $"] = dollar if dollar is not None else ""

        rows.append(disp)
        export_rows.append(export)

    display_df = pd.DataFrame(rows)

    styled = (
        display_df.style
        .applymap(_color_cell, subset=PERIODS)
        .set_properties(subset=["Ticker"], **{"font-weight": "bold"})
        .set_properties(subset=["Mentions", "Posts"], **{"text-align": "center"})
        .set_properties(subset=["Price"], **{"text-align": "right", "font-weight": "600"})
        .hide(axis="index")
    )
    st.dataframe(styled, use_container_width=True, height=min(60 + len(rows) * 38, 600))

    # ── Sample mentions (expandable) ──
    with st.expander("💬 See sample Reddit mentions for each ticker"):
        for _, r in top_df.iterrows():
            samples = r["_samples"]
            if not samples:
                continue
            st.markdown(f"**{r['Ticker']}** — {r['Sentiment']}")
            for s in samples[:3]:
                emoji = "🟢" if s["sentiment"] > 0 else "🔴" if s["sentiment"] < 0 else "⚪"
                st.caption(f"{emoji} *r/{s['subreddit']}*: {s['text']}")
            st.divider()

    # ── Export ──
    export_df = pd.DataFrame(export_rows)
    csv = export_df.to_csv(index=False)
    fname = f"reddit_{label.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    st.download_button(f"⬇ Export {label} CSV", csv, fname, "text/csv")


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    st.subheader("Scan Parameters")
    days = st.slider("Days to look back", 1, 90, 7)
    min_mentions = st.number_input("Min mentions threshold", 1, 500, 5, step=1)
    scan_mode = st.selectbox("Scan depth", list(SCAN_LIMITS.keys()), index=0)
    top_n = st.number_input("Top N recommendations", 1, 100, 10, step=1)

    st.divider()
    st.subheader("Subreddit Filters")
    min_subscribers = st.number_input("Min subscribers", 0, 20_000_000, 0, step=10000, format="%d")
    selected_categories = st.multiselect("Categories", CATEGORIES, default=CATEGORIES)

    st.divider()
    st.subheader("Manage Subreddits")

    with st.expander("➕ Add Subreddit"):
        new_name = st.text_input("Name (no r/)")
        new_cat  = st.selectbox("Category", CATEGORIES, key="new_cat")
        new_subs = st.number_input("Approx subscribers", 0, 20_000_000, 1000, key="new_subs")
        if st.button("Add") and new_name.strip():
            name = new_name.strip().lstrip("r/")
            if name.lower() not in [s["name"].lower() for s in st.session_state.subreddits]:
                st.session_state.subreddits.append({"name": name, "category": new_cat, "subscribers": new_subs, "enabled": True})
                st.success(f"Added r/{name}")
                st.rerun()
            else:
                st.warning("Already in list.")

    st.markdown("**Active Subreddits:**")
    to_delete = None
    for i, sub in enumerate(st.session_state.subreddits):
        if sub["subscribers"] < min_subscribers or sub["category"] not in selected_categories:
            continue
        col_chk, col_lbl, col_del = st.columns([1, 5, 1])
        with col_chk:
            enabled = st.checkbox(" ", value=sub["enabled"], key=f"chk_{i}", label_visibility="collapsed")
            st.session_state.subreddits[i]["enabled"] = enabled
        with col_lbl:
            icon = {"Stocks": "📊", "Crypto": "🪙", "Options": "⚡"}.get(sub["category"], "")
            st.caption(f"{icon} r/{sub['name']} ({sub['subscribers']:,})")
        with col_del:
            if st.button("🗑", key=f"del_{i}", help=f"Remove r/{sub['name']}"):
                to_delete = i

    if to_delete is not None:
        st.session_state.subreddits.pop(to_delete)
        st.rerun()

    st.divider()
    run_scan = st.button("🚀 Run Scan", type="primary", use_container_width=True)
    if st.button("🗑 Clear Price Cache", use_container_width=True):
        st.session_state.perf_cache = {}
        st.success("Price cache cleared.")


# ── Main area ────────────────────────────────────────────────────────────────
st.title("📈 Reddit Investment Advisor")
st.caption(f"Reddit access: **{auth_mode()}** · Not financial advice.")

if run_scan:
    active = [
        s for s in st.session_state.subreddits
        if s["enabled"] and s["category"] in selected_categories and s["subscribers"] >= min_subscribers
    ]
    if not active:
        st.warning("No subreddits selected. Adjust your filters.")
    else:
        cfg          = SCAN_LIMITS[scan_mode]
        max_posts    = cfg["posts"]
        max_comments = cfg["comments"]
        sub_names    = [s["name"] for s in active]
        total        = len(sub_names)

        cache_key = (tuple(sorted(sub_names)), days, max_posts, max_comments)
        cached = st.session_state.cache.get(cache_key)

        if cached and (time.time() - cached[0]) < CACHE_TTL:
            st.session_state.results = aggregate_mentions(cached[1], min_mentions=int(min_mentions))
            st.session_state.scan_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state.perf_cache = {}   # clear stale prices on new scan
            st.success(f"✨ Results from cache (< 5 min old). {len(cached[1]):,} items.")
        else:
            t_start      = time.time()
            progress_bar = st.progress(0)
            status_text  = st.empty()
            eta_text     = st.empty()
            log_box      = st.empty()
            log_lines    = []

            def on_progress(subreddit, items_found, elapsed, done, total):
                pct = done / total
                eta = (elapsed / done) * (total - done) if done else 0
                progress_bar.progress(pct)
                status_text.markdown(
                    f"**{done}/{total} subreddits done** · just finished `r/{subreddit}` ({items_found} items)"
                )
                eta_text.markdown(
                    f"⏱ **{elapsed:.1f}s** elapsed &nbsp;|&nbsp; ETA **{eta:.0f}s** &nbsp;|&nbsp; **{pct*100:.0f}%** complete"
                )
                log_lines.append(f"✅  r/{subreddit:<22} {items_found:>5} items")
                log_box.code("\n".join(log_lines[-10:]))

            all_texts = scan_all(sub_names, int(days), max_posts, max_comments, on_progress)

            progress_bar.empty()
            status_text.empty()
            eta_text.empty()
            log_box.empty()

            duration = time.time() - t_start

            if all_texts:
                st.session_state.cache[cache_key] = (time.time(), all_texts)
                st.session_state.results       = aggregate_mentions(all_texts, min_mentions=int(min_mentions))
                st.session_state.scan_time     = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state.scan_duration = duration
                st.session_state.perf_cache    = {}   # fresh prices on new scan
                st.success(f"✅ Done in **{duration:.1f}s** — {len(all_texts):,} text items from {total} subreddits.")
            else:
                st.error(
                    "⚠️ **No data retrieved from Reddit.**\n\n"
                    "If you're running on Streamlit Cloud, Reddit may be blocking the datacenter IP. "
                    "Possible fixes:\n"
                    "1. Wait 60 seconds and retry (transient rate-limit)\n"
                    "2. Try a smaller subreddit list or **Turbo** scan mode\n"
                    "3. Configure Reddit OAuth credentials in Streamlit secrets (see README)"
                )

# ── Results tabs ─────────────────────────────────────────────────────────────
if st.session_state.results:
    dur = f" in {st.session_state.scan_duration:.1f}s" if st.session_state.scan_duration else ""
    st.caption(f"Last scan: {st.session_state.scan_time}{dur}")

    tab_all, tab_stocks, tab_options, tab_crypto = st.tabs([
        "🌐 All", "📊 Stocks", "⚡ Options", "🪙 Crypto"
    ])
    with tab_all:
        render_results_tab(results_to_df(st.session_state.results), "All", int(top_n))
    with tab_stocks:
        render_results_tab(results_to_df(st.session_state.results, "Stocks"), "Stocks", int(top_n))
    with tab_options:
        render_results_tab(results_to_df(st.session_state.results, "Options"), "Options", int(top_n))
    with tab_crypto:
        render_results_tab(results_to_df(st.session_state.results, "Crypto"), "Crypto", int(top_n))
else:
    st.info("👈 Configure parameters in the sidebar and click **Run Scan**.")
