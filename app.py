import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from curl_cffi import requests as cffi_requests

st.title("Stock Dashboard")

# A session that impersonates a real browser, so Yahoo Finance doesn't
# block requests coming from cloud servers (a common issue when deploying).
session = cffi_requests.Session(impersonate="chrome")

# ---- Welcome / name personalization ----
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

name_input = st.text_input("What's your name?", st.session_state.user_name)
if name_input:
    st.session_state.user_name = name_input
    st.write(f"Welcome, {name_input}! 👋")

@st.cache_data(ttl=3600)  # cache results for 1 hour
def get_stock_info(symbol):
    try:
        return yf.Ticker(symbol, session=session).info
    except Exception:
        return {}

@st.cache_data(ttl=3600)
def get_stock_history(symbol, period="6mo"):
    try:
        return yf.Ticker(symbol, session=session).history(period=period)
    except Exception:
        return pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["Market Overview", "Single Stock", "Screener"])

# ---- TAB 1: Market Overview ----
with tab1:
    st.write("Most recent trading day's performance. (Markets are closed on weekends and holidays, so this reflects the last session.)")

    indices = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI"
    }

    cols = st.columns(len(indices))
    for col, (name, symbol) in zip(cols, indices.items()):
        data = get_stock_history(symbol, "2d")
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            latest = data["Close"].iloc[-1]
            pct_change = ((latest - prev_close) / prev_close) * 100
            col.metric(name, f"{latest:,.2f}", f"{pct_change:+.2f}%")

    st.subheader("Your watchlist: today's movers")

    watchlist = [
        "AAPL", "MSFT", "TSLA", "NVDA", "JPM", "AMZN", "GOOGL", "META", "KO", "PFE",
        "WMT", "DIS", "NFLX", "XOM", "BA", "V", "MA", "HD", "PG", "INTC",
        "ADBE", "CRM", "COST", "PEP", "UNH", "CVX", "ABBV", "MRK", "AVGO", "ORCL",
        "T", "VZ", "NKE", "MCD", "SBUX", "LMT", "CAT", "GE", "IBM", "GS"
    ]

    rows = []
    for sym in watchlist:
        data = get_stock_history(sym, "2d")
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            latest = data["Close"].iloc[-1]
            pct_change = ((latest - prev_close) / prev_close) * 100
            rows.append({"Ticker": sym, "Price": round(latest, 2), "% Change Today": round(pct_change, 2)})

    df = pd.DataFrame(rows).sort_values("% Change Today", ascending=False)
    st.dataframe(df, width="stretch")

# ---- TAB 2: Single stock lookup ----
with tab2:
    symbol = st.text_input("Enter a stock ticker (e.g. AAPL, TSLA, MSFT)", "AAPL")

    if symbol:
        info = get_stock_info(symbol)

        if not info or info.get("currentPrice") is None:
            st.error(f"Couldn't find data for '{symbol}'. Double check the ticker symbol and try again.")
        else:
            st.subheader(info.get("longName", symbol))

            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"${info.get('currentPrice', 0):.2f}")
            col2.metric("P/E Ratio", info.get("trailingPE", "N/A"))
            col3.metric("Market Cap", f"{info.get('marketCap', 0):,}")

            history = get_stock_history(symbol, "6mo")

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
                        st.success(f"📈 Trending Up — price (\\${current_price:.2f}) is above its 50-day average (\\${current_avg:.2f})")
                    else:
                        st.error(f"📉 Trending Down — price (\\${current_price:.2f}) is below its 50-day average (\\${current_avg:.2f})")

            with vol_col:
                if annualized_volatility < 25:
                    st.info(f"🟢 Lower volatility — {annualized_volatility:.1f}% annualized")
                elif annualized_volatility < 50:
                    st.warning(f"🟡 Moderate volatility — {annualized_volatility:.1f}% annualized")
                else:
                    st.error(f"🔴 High volatility — {annualized_volatility:.1f}% annualized")

            st.line_chart(history[["Close", "50-Day Avg"]])

# ---- TAB 3: Screener ----
with tab3:
    st.write("Filter stocks by P/E ratio and market cap.")

    watchlist = [
        "AAPL", "MSFT", "TSLA", "NVDA", "JPM", "AMZN", "GOOGL", "META", "KO", "PFE",
        "WMT", "DIS", "NFLX", "XOM", "BA", "V", "MA", "HD", "PG", "INTC",
        "ADBE", "CRM", "COST", "PEP", "UNH", "CVX", "ABBV", "MRK", "AVGO", "ORCL",
        "T", "VZ", "NKE", "MCD", "SBUX", "LMT", "CAT", "GE", "IBM", "GS"
    ]

    col1, col2 = st.columns(2)
    max_pe = col1.slider("Maximum P/E ratio", min_value=0, max_value=100, value=40)
    min_cap_b = col2.slider("Minimum market cap ($ billions)", min_value=0, max_value=3000, value=0)

    rows = []
    for sym in watchlist:
        data = get_stock_info(sym)
        pe = data.get("trailingPE")
        cap = data.get("marketCap")
        if pe is not None and cap is not None:
            if pe <= max_pe and cap >= min_cap_b * 1_000_000_000:
                rows.append({
                    "Ticker": sym,
                    "Name": data.get("longName", sym),
                    "Price": data.get("currentPrice"),
                    "P/E Ratio": round(pe, 2),
                    "Market Cap ($B)": round(cap / 1_000_000_000, 1),
                })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch")
    else:
        st.write("No stocks match that filter.")
