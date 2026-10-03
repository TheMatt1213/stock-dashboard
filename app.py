import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Stock Dashboard")

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
        data = yf.Ticker(symbol).history(period="2d")
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            latest = data["Close"].iloc[-1]
            pct_change = ((latest - prev_close) / prev_close) * 100
            col.metric(name, f"{latest:,.2f}", f"{pct_change:+.2f}%")

    st.subheader("Your watchlist: today's movers")

    watchlist = [
        "AAPL", "MSFT", "TSLA", "NVDA", "JPM", "AMZN", "GOOGL", "META", "KO", "PFE"
    ]

    rows = []
    for sym in watchlist:
        data = yf.Ticker(sym).history(period="2d")
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
        ticker = yf.Ticker(symbol)
        info = ticker.info

        st.subheader(info.get("longName", symbol))

        col1, col2, col3 = st.columns(3)
        col1.metric("Price", f"${info.get('currentPrice', 0):.2f}")
        col2.metric("P/E Ratio", info.get("trailingPE", "N/A"))
        col3.metric("Market Cap", f"{info.get('marketCap', 0):,}")

        history = ticker.history(period="6mo")

        # Calculate the 50-day moving average
        history["50-Day Avg"] = history["Close"].rolling(window=50).mean()

        current_price = history["Close"].iloc[-1]
        current_avg = history["50-Day Avg"].iloc[-1]

        if pd.notna(current_avg):
            if current_price > current_avg:
                           st.success(f"📈 Trending Up — current price (\\${current_price:.2f}) is above its 50-day average (\\${current_avg:.2f})")
            else:
                st.error(f"📉 Trending Down — current price (\\${current_price:.2f}) is below its 50-day average (\\${current_avg:.2f})")   

        st.line_chart(history[["Close", "50-Day Avg"]])

# ---- TAB 3: Screener ----
with tab3:
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
        st.dataframe(df, width="stretch")
    else:
        st.write("No stocks match that filter.")
