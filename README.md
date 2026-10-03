# Stock Dashboard

A live stock market dashboard built with Python and Streamlit — pulls real-time data to show market trends, individual stock analysis, and a filterable stock screener.

**[Live App](https://stock-dashboard-8bxyv2wxmvtupf4rffmqou.streamlit.app)**

## Features

- **Market Overview** — live performance of the S&P 500, Nasdaq, and Dow Jones, plus a sortable table of the day's biggest movers across a 40-stock watchlist.
- **Single Stock Lookup** — search any ticker to see price, P/E ratio, and market cap, along with:
  - A 6-month price chart with a 50-day moving average overlay to show trend direction
  - Annualized volatility, calculated from daily price swings, to gauge how risky/choppy the stock currently is
- **Screener** — filter a 40-stock watchlist by maximum P/E ratio and minimum market cap to surface stocks matching specific value/size criteria.

## Tech Stack

- **Python** — core language
- **Streamlit** — web app framework/UI
- **yfinance** — live market data from Yahoo Finance
- **pandas / numpy** — data handling and calculations (moving averages, volatility)
- **curl_cffi** — browser-impersonating HTTP sessions (see "Deployment notes" below)

## Why these features

- **P/E ratio & market cap filters** mirror real value-investing screens — filtering for reasonably-priced, established companies.
- **50-day moving average** is a standard technical analysis tool: price above the average generally signals an uptrend, below signals a downtrend.
- **Annualized volatility** (standard deviation of daily returns, scaled by √252 trading days) is the standard way analysts quantify how risky a stock's price movement is.

## Performance

Stock data is cached for 1 hour (`st.cache_data`) to avoid redundant API calls and keep the app fast when filtering or switching between stocks.

## Deployment notes

During deployment, Yahoo Finance began blocking data requests coming from Streamlit Cloud's servers (a common anti-bot measure against cloud/datacenter IPs), even though the app worked fine locally. Fixed by routing requests through `curl_cffi`, which impersonates a real browser's request signature.

## Scaling notes

This project uses a curated 40-stock watchlist and a free data source (`yfinance`), which is appropriate for a student/portfolio project. A production version supporting the full market would require:
- A paid bulk market data provider (e.g. Polygon.io, IEX Cloud)
- A database to store periodically-refreshed data instead of live per-request fetching
- A scheduled job to refresh that data on an interval

## Future improvements

- Sector-level trend comparisons
- Apply trend/volatility indicators within the Screener itself
- User accounts to save personal watchlists

---

Built by Matthew — finance student, exploring the intersection of markets and code.
