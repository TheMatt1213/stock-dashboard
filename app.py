import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Stock Dashboard")

tab1, tab2 = st.tabs(["Single Stock", "Screener"])

# ---- TAB 1: Single stock lookup (what you already had) ----
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
    st.write("Filter a list of stocks by P/E ratio.")

    # A starter watchlist — you can expand this list later
    watchlist = ["AAPL", "MSFT", "TSLA", "NVDA", "JPM", "AMZN", "GOOGL", "META", "KO", "PFE"]

    max_pe = st.slider("Maximum P/E ratio", min_value=0, max_value=100, value=40)

    rows = []
    for sym in watchlist:
        data = yf.Ticker(sym).info
        pe = data.get("trailingPE")
        if pe is not None and pe <= max_pe:
            rows.append({
                "Ticker": sym,
                "Name": data.get("longName", sym),
                "Price": data.get("currentPrice"),
                "P/E Ratio": round(pe, 2),
                "Market Cap": data.get("marketCap"),
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
    else:
        st.write("No stocks in the watchlist match that filter.")