import time

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from curl_cffi import requests as cffi_requests

st.title("Stock Dashboard")

# A session that impersonates a real browser, so Yahoo Finance is less likely
# to block requests coming from cloud servers.
session = cffi_requests.Session(impersonate="chrome")

# ---- Welcome / name personalization ----
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

name_input = st.text_input("What's your name?", st.session_state.user_name)
if name_input:
    st.session_state.user_name = name_input
    st.write(f"Welcome, {name_input}! 👋")


# ---------------------------------------------------------------------------
# Data helpers
#
# Important: the cached functions RAISE an error when Yahoo gives back nothing.
# Streamlit does not cache a function that raises, so one bad moment (for
# example right after the app wakes up) is never remembered. The wrapper
# functions below catch the error, retry, and return an empty result.
# ---------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_info(symbol):
    info = yf.Ticker(symbol, session=session).info
    if not info or (
        info.get("currentPrice") is None
        and info.get("trailingPE") is None
        and info.get("marketCap") is None
    ):
        raise ValueError(f"No info returned for {symbol}")
    return info


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_fast(symbol):
    fi = yf.Ticker(symbol, session=session).fast_info
    price = fi["lastPrice"]
    cap = fi["marketCap"]
    if price is None and cap is None:
        raise ValueError(f"No fast info returned for {symbol}")
    return {"price": price, "market_cap": cap}


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_history(symbol, period):
    history = yf.Ticker(symbol, session=session).history(period=period)
    if history is None or history.empty:
        raise ValueError(f"No price history returned for {symbol}")
    return history


def _with_retries(fn, *args, retries=1, delay=1.0):
    for attempt in range(retries):
        try:
            return fn(*args)
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay)
    return None


def get_stock_info(symbol, retries=2):
    return _with_retries(_fetch_info, symbol, retries=retries) or {}


def get_fast_info(symbol, retries=2):
    return _with_retries(_fetch_fast, symbol, retries=retries) or {}


def get_stock_history(symbol, period="6mo", retries=2):
    result = _with_retries(_fetch_history, symbol, period, retries=retries)
    return result if result is not None else pd.DataFrame()


def retry_button(key):
    """Lets a visitor clear saved results and try again."""
    if st.button("Try again", key=key):
        st.cache_data.clear()
        st.rerun()


WATCHLIST = [
    "AAPL", "MSFT", "TSLA", "NVDA", "JPM", "AMZN", "GOOGL", "META", "KO", "PFE",
    "WMT", "DIS", "NFLX", "XOM", "BA", "V", "MA", "HD", "PG", "INTC",
    "ADBE", "CRM", "COST", "PEP", "UNH", "CVX", "ABBV", "MRK", "AVGO", "ORCL",
    "T", "VZ", "NKE", "MCD", "SBUX", "LMT", "CAT", "GE", "IBM", "GS",
]

tab1, tab2, tab3 = st.tabs(["Market Overview", "Single Stock", "Screener"])

# ---- TAB 1: Market Overview ----
with tab1:
    st.write(
        "Most recent trading day's performance. (Markets are closed on weekends "
        "and holidays, so this reflects the last session.)"
    )

    indices = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Dow Jones": "^DJI"}

    cols = st.columns(len(indices))
    for col, (name, index_symbol) in zip(cols, indices.items()):
        data = get_stock_history(index_symbol, "2d", retries=2)
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            latest = data["Close"].iloc[-1]
            pct_change = ((latest - prev_close) / prev_close) * 100
            col.metric(name, f"{latest:,.2f}", f"{pct_change:+.2f}%")
        else:
            col.metric(name, "N/A")

    st.subheader("Your watchlist: today's movers")

    rows = []
    for sym in WATCHLIST:
        data = get_stock_history(sym, "2d", retries=1)
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            latest = data["Close"].iloc[-1]
            pct_change = ((latest - prev_close) / prev_close) * 100
            rows.append(
                {
                    "Ticker": sym,
                    "Price": round(latest, 2),
                    "% Change Today": round(pct_change, 2),
                }
            )

    if rows:
        df = pd.DataFrame(rows).sort_values("% Change Today", ascending=False)
        st.dataframe(df, width="stretch")
    else:
        st.warning("Market data is temporarily unavailable.")
        retry_button("retry_market")

# ---- TAB 2: Single stock lookup ----
with tab2:
    symbol = st.text_input(
        "Enter a stock ticker (e.g. AAPL, TSLA, MSFT)", "AAPL"
    ).strip().upper()

    if symbol:
        info = get_stock_info(symbol, retries=2)
        fast = get_fast_info(symbol, retries=1)
        history = get_stock_history(symbol, "6mo", retries=2)

        # Prefer the detailed data, but fall back to lighter sources so the
        # page still shows something useful if Yahoo blocks the detailed one.
        price = info.get("currentPrice") or fast.get("price")
        if price is None and not history.empty:
            price = float(history["Close"].iloc[-1])

        if price is None and history.empty:
            st.error(
                f"Couldn't load data for '{symbol}'. Check the ticker symbol. If it "
                "is correct, Yahoo Finance may be temporarily unavailable, so try "
                "again in a moment."
            )
            retry_button("retry_single")
        else:
            st.subheader(info.get("longName", symbol))

            pe_ratio = info.get("trailingPE")
            market_cap = info.get("marketCap") or fast.get("market_cap")

            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"${price:,.2f}" if price else "N/A")
            col2.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
            col3.metric(
                "Market Cap",
                f"${market_cap / 1_000_000_000:,.1f}B" if market_cap else "N/A",
            )

            if not info:
                st.caption(
                    "Some details (like the P/E ratio) are unavailable right now "
                    "because Yahoo Finance is limiting requests."
                )
                retry_button("retry_details")

            if not history.empty:
                history = history.copy()
                history["50-Day Avg"] = history["Close"].rolling(window=50).mean()
                history["Daily Return"] = history["Close"].pct_change()
                daily_volatility = history["Daily Return"].std()
                annualized_volatility = daily_volatility * np.sqrt(252) * 100

                current_price = history["Close"].iloc[-1]
                current_avg = history["50-Day Avg"].iloc[-1]

                trend_col, vol_col = st.columns(2)

                with trend_col:
                    if pd.notna(current_avg):
                        if current_price > current_avg:
                            st.success(
                                f"📈 Trending Up: price (\\${current_price:.2f}) is above "
                                f"its 50-day average (\\${current_avg:.2f})"
                            )
                        else:
                            st.error(
                                f"📉 Trending Down: price (\\${current_price:.2f}) is below "
                                f"its 50-day average (\\${current_avg:.2f})"
                            )

                with vol_col:
                    if pd.notna(annualized_volatility):
                        if annualized_volatility < 25:
                            st.info(
                                f"🟢 Lower volatility: {annualized_volatility:.1f}% annualized"
                            )
                        elif annualized_volatility < 50:
                            st.warning(
                                f"🟡 Moderate volatility: {annualized_volatility:.1f}% annualized"
                            )
                        else:
                            st.error(
                                f"🔴 High volatility: {annualized_volatility:.1f}% annualized"
                            )

                st.line_chart(history[["Close", "50-Day Avg"]])

# ---- TAB 3: Screener ----
with tab3:
    st.write("Filter stocks by P/E ratio and market cap.")

    col1, col2 = st.columns(2)
    max_pe = col1.slider("Maximum P/E ratio", min_value=0, max_value=100, value=40)
    min_cap_b = col2.slider(
        "Minimum market cap ($ billions)", min_value=0, max_value=3000, value=0
    )

    rows = []
    checked = 0
    failed_in_a_row = 0
    gave_up = False

    for sym in WATCHLIST:
        data = get_stock_info(sym, retries=1)
        if not data:
            failed_in_a_row += 1
            # If Yahoo is blocking us, stop early instead of making the
            # visitor wait through dozens of failed requests.
            if failed_in_a_row >= 5 and checked == 0:
                gave_up = True
                break
            continue

        failed_in_a_row = 0
        checked += 1
        pe = data.get("trailingPE")
        cap = data.get("marketCap")
        if pe is not None and cap is not None:
            if pe <= max_pe and cap >= min_cap_b * 1_000_000_000:
                rows.append(
                    {
                        "Ticker": sym,
                        "Name": data.get("longName", sym),
                        "Price": data.get("currentPrice"),
                        "P/E Ratio": round(pe, 2),
                        "Market Cap ($B)": round(cap / 1_000_000_000, 1),
                    }
                )

    if gave_up:
        st.warning(
            "Stock details are temporarily unavailable because Yahoo Finance is "
            "limiting requests. Please try again in a moment."
        )
        retry_button("retry_screener")
    elif rows:
        st.dataframe(pd.DataFrame(rows), width="stretch")
        if checked < len(WATCHLIST):
            st.caption(
                f"Checked {checked} of {len(WATCHLIST)} stocks. Some couldn't be "
                "loaded right now."
            )
    else:
        st.write("No stocks match that filter.")
        if checked < len(WATCHLIST):
            st.caption(
                f"Only {checked} of {len(WATCHLIST)} stocks could be loaded right now."
            )
            retry_button("retry_screener_partial")
