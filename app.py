import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Stock Dashboard")

tab1, tab2 = st.tabs(["Single Stock", "Screener"])

# ---- TAB 1: Single stock lookup ----
with tab1:
    symbol = st.text_input("Enter a stock ticker (e.g. AAPL, TSLA, MSFT)", "AAPL")

    if symbol:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        st.subheader(info.get("longName", symbol))

        col1, col2, col3 = st.columns(3)
        col1.metric("Price", f"${info.get('currentPrice', 0):.2f}")
        col2.metric("P/E Ratio", info.get("trailingPE", "N/A"))
        col3.metric("Market Cap", f"{info.get('marketCap', 0):,}")

        history = ticker.history(period="6mo")
        st.line_chart(history["Close"])

# ---- TAB 2: Screener across multiple stocks ----
with tab2:
    st.write("Filter stocks by P/E ratio and market cap.")

    watchlist = [
        "AAPL", "MSFT", "TSLA", "NVDA", "JPM", "AMZN", "GOOGL", "META", "KO", "PFE",
        "WMT", "DIS", "NFLX", "XOM", "BA", "V", "MA", "HD", "PG", "INTC"
    ]

    col1, col2 = st.columns(2)
    max_pe = col1.slider("Maximum P/E ratio", min_value=0, max_value=100, value=40)
    min_cap_b = col2.slider("Minimum market cap ($ billions)", min_value=0, max_value=3000, value=0)

    rows = []
    for sym in watchlist:
        data = yf.Ticker(sym).info
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
        st.dataframe(df, use_container_width=True)
    else:
        st.write("No stocks match that filter.")
