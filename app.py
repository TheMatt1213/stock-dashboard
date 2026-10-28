import time

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from curl_cffi import requests as cffi_requests

st.title("Stock Dashboard")

# A session that impersonates a real browser, so Yahoo Finance is less likely
# to block requests coming from cloud servers.
session = cffi_requests.Session(impersonate="chrome")

# Free Finnhub API key, stored in Streamlit's "Secrets" (never in the code).
try:
    FINNHUB_KEY = st.secrets["FINNHUB_KEY"]
except Exception:
    FINNHUB_KEY = ""

# ---- Welcome / name personalization ----
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

name_input = st.text_input("What's your name?", st.session_state.user_name)
if name_input:
    st.session_state.user_name = name_input
    st.write(f"Welcome, {name_input}! 👋")

COMPANY_NAMES = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "TSLA": "Tesla Inc.",
    "NVDA": "NVIDIA Corp.", "JPM": "JPMorgan Chase & Co.", "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.", "META": "Meta Platforms Inc.", "KO": "Coca-Cola Co.",
    "PFE": "Pfizer Inc.", "WMT": "Walmart Inc.", "DIS": "Walt Disney Co.",
    "NFLX": "Netflix Inc.", "XOM": "Exxon Mobil Corp.", "BA": "Boeing Co.",
    "V": "Visa Inc.", "MA": "Mastercard Inc.", "HD": "Home Depot Inc.",
    "PG": "Procter & Gamble Co.", "INTC": "Intel Corp.", "ADBE": "Adobe Inc.",
    "CRM": "Salesforce Inc.", "COST": "Costco Wholesale Corp.", "PEP": "PepsiCo Inc.",
    "UNH": "UnitedHealth Group Inc.", "CVX": "Chevron Corp.", "ABBV": "AbbVie Inc.",
    "MRK": "Merck & Co. Inc.", "AVGO": "Broadcom Inc.", "ORCL": "Oracle Corp.",
    "T": "AT&T Inc.", "VZ": "Verizon Communications Inc.", "NKE": "Nike Inc.",
    "MCD": "McDonald's Corp.", "SBUX": "Starbucks Corp.", "LMT": "Lockheed Martin Corp.",
    "CAT": "Caterpillar Inc.", "GE": "GE Aerospace", "IBM": "IBM",
    "GS": "Goldman Sachs Group Inc.",
}

WATCHLIST = list(COMPANY_NAMES.keys())


# ---------------------------------------------------------------------------
# Data helpers
#
# Important: the cached functions RAISE an error when a source gives back
# nothing. Streamlit does not cache a function that raises, so one bad moment
# (for example right after the app wakes up) is never remembered. The wrapper
# functions below catch the error, retry, and return an empty result.
#
# Data sources: Finnhub (free API key) for P/E, market cap, name and price.
# Yahoo Finance (yfinance) for price history, and as a backup for the rest.
# ---------------------------------------------------------------------------
def _finnhub_get(path, **params):
    url = f"https://finnhub.io/api/v1/{path}"
    params["token"] = FINNHUB_KEY
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 429:  # rate limited: wait briefly, try once more
        time.sleep(2)
        resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_finnhub_fundamentals(symbol):
    metric = (_finnhub_get("stock/metric", symbol=symbol, metric="all") or {}).get(
        "metric"
    ) or {}
    pe = None
    for key in ("peTTM", "peBasicExclExtraTTM", "peNormalizedAnnual"):
        if metric.get(key):
            pe = metric[key]
            break
    cap_millions = metric.get("marketCapitalization")  # Finnhub reports millions
    if pe is None and not cap_millions:
        raise ValueError(f"No fundamentals returned for {symbol}")
    return {
        "trailingPE": pe,
        "marketCap": cap_millions * 1_000_000 if cap_millions else None,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_finnhub_profile(symbol):
    profile = _finnhub_get("stock/profile2", symbol=symbol) or {}
    quote = _finnhub_get("quote", symbol=symbol) or {}
    name = profile.get("name")
    price = quote.get("c") or None
    if not name and not price:
        raise ValueError(f"No profile returned for {symbol}")
    return {"longName": name, "currentPrice": price}


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
    """Yahoo's detailed data (used only as a backup)."""
    return _with_retries(_fetch_info, symbol, retries=retries) or {}


def get_fast_info(symbol, retries=2):
    return _with_retries(_fetch_fast, symbol, retries=retries) or {}


def get_stock_history(symbol, period="6mo", retries=2):
    result = _with_retries(_fetch_history, symbol, period, retries=retries)
    return result if result is not None else pd.DataFrame()


def get_fundamentals(symbol, retries=1):
    """P/E ratio and market cap. Finnhub first, Yahoo as a backup."""
    if FINNHUB_KEY:
        data = _with_retries(_fetch_finnhub_fundamentals, symbol, retries=retries)
        if data:
            return data
    info = get_stock_info(symbol, retries=retries)
    if info:
        return {"trailingPE": info.get("trailingPE"), "marketCap": info.get("marketCap")}
    return {}


def get_profile(symbol, retries=1):
    """Company name and current price. Finnhub first, Yahoo as a backup."""
    if FINNHUB_KEY:
        data = _with_retries(_fetch_finnhub_profile, symbol, retries=retries)
        if data:
            return data
    info = get_stock_info(symbol, retries=retries)
    if info:
        return {"longName": info.get("longName"), "currentPrice": info.get("currentPrice")}
    return {}


def retry_button(key):
    """Lets a visitor clear saved results and try again."""
    if st.button("Try again", key=key):
        st.cache_data.clear()
        st.rerun()


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
        history = get_stock_history(symbol, "6mo", retries=2)
        fund = get_fundamentals(symbol, retries=2)
        profile = get_profile(symbol, retries=2)

        price = profile.get("currentPrice")
        if price is None and not history.empty:
            price = float(history["Close"].iloc[-1])

        pe_ratio = fund.get("trailingPE")
        market_cap = fund.get("marketCap")
        if market_cap is None:
            market_cap = get_fast_info(symbol, retries=1).get("market_cap")

        if price is None and history.empty:
            st.error(
                f"Couldn't load data for '{symbol}'. Check the ticker symbol. If it "
                "is correct, the data source may be temporarily unavailable, so try "
                "again in a moment."
            )
            retry_button("retry_single")
        else:
            st.subheader(profile.get("longName") or COMPANY_NAMES.get(symbol, symbol))

            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"${price:,.2f}" if price else "N/A")
            col2.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
            col3.metric(
                "Market Cap",
                f"${market_cap / 1_000_000_000:,.1f}B" if market_cap else "N/A",
            )

            if not fund:
                st.caption(
                    "Some details (like the P/E ratio) are unavailable right now "
                    "because the data source is limiting requests."
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
        data = get_fundamentals(sym, retries=1)
        if not data:
            failed_in_a_row += 1
            # If the data source is blocking us, stop early instead of making
            # the visitor wait through dozens of failed requests.
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
                hist = get_stock_history(sym, "2d", retries=1)
                price = round(float(hist["Close"].iloc[-1]), 2) if not hist.empty else None
                rows.append(
                    {
                        "Ticker": sym,
                        "Name": COMPANY_NAMES.get(sym, sym),
                        "Price": price,
                        "P/E Ratio": round(pe, 2),
                        "Market Cap ($B)": round(cap / 1_000_000_000, 1),
                    }
                )

    if gave_up:
        st.warning(
            "Stock details are temporarily unavailable because the data source is "
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
