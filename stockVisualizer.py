import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import yfinance as yf
import datetime as dt
from mplfinance.original_flavor import candlestick_ohlc

smasUsed = [20]

stock = input("Enter a ticker symbol: ")

while stock.lower() != "quit":
    start = input("Enter Start Date (YYYY-MM-DD): ")
    end = input("Enter End Date (YYYY-MM-DD): ")

    prices = yf.download(stock, start=start, end=end, auto_adjust=False)

    if prices.empty:
        print("No data found. Check ticker/date range.")
        stock = input("Enter the ticker Symbol : ")
        continue

    # Flatten MultiIndex columns if present
    if isinstance(prices.columns, pd.MultiIndex):
        prices.columns = prices.columns.get_level_values(0)

    close_col = "Adj Close" if "Adj Close" in prices.columns else "Close"

    # -----------------------------
    # Moving averages
    # -----------------------------
    for sma in smasUsed:
        prices[f"SMA_{sma}"] = prices[close_col].rolling(window=sma).mean()

    # -----------------------------
    # Bollinger Bands
    # -----------------------------
    BBperiod = 20
    stdev = 2
    prices[f"SMA{BBperiod}"] = prices[close_col].rolling(window=BBperiod).mean()
    prices["STDEV"] = prices[close_col].rolling(window=BBperiod).std()
    prices["LowerBand"] = prices[f"SMA{BBperiod}"] - (stdev * prices["STDEV"])
    prices["UpperBand"] = prices[f"SMA{BBperiod}"] + (stdev * prices["STDEV"])

    # -----------------------------
    # Stochastic oscillator
    # -----------------------------
    Period = 10
    K = 4
    D = 4
    prices["RolHigh"] = prices["High"].rolling(window=Period).max()
    prices["RolLow"] = prices["Low"].rolling(window=Period).min()

    denom = (prices["RolHigh"] - prices["RolLow"]).replace(0, np.nan)
    prices["stok"] = ((prices[close_col] - prices["RolLow"]) / denom) * 100
    prices["K"] = prices["stok"].rolling(window=K).mean()
    prices["D"] = prices["K"].rolling(window=D).mean()

    # Create date column for candlestick plotting
    prices["Date"] = mdates.date2num(prices.index.to_pydatetime())

    # Remove early rows with NaNs from indicators
    min_bars = max(max(smasUsed), BBperiod, Period + K + D)
    prices = prices.iloc[min_bars:].copy()

    if prices.empty:
        print("Not enough data after indicator calculations.")
        stock = input("Enter the ticker Symbol : ")
        continue

    # -----------------------------
    # Zoom window for readability
    # -----------------------------
    zoom_days = 200
    prices = prices.tail(zoom_days).copy()

    # -----------------------------
    # Build OHLC list
    # -----------------------------
    ohlc = []
    for i in prices.index:
        ohlc.append((
            prices.loc[i, "Date"],
            prices.loc[i, "Open"],
            prices.loc[i, "High"],
            prices.loc[i, "Low"],
            prices.loc[i, close_col],
            prices.loc[i, "Volume"]
        ))

    # -----------------------------
    # Plot setup
    # -----------------------------
    fig, (ax1, ax2) = plt.subplots(
        2, 1,
        figsize=(15, 10),
        dpi=120,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]}
    )

    # -----------------------------
    # Price chart
    # -----------------------------
    candlestick_ohlc(ax1, ohlc, width=0.5, colorup="green", colordown="red", alpha=0.8)

    for sma in smasUsed:
        ax1.plot(prices["Date"], prices[f"SMA_{sma}"], label=f"SMA {sma}", linewidth=1.3)

    ax1.plot(prices["Date"], prices["UpperBand"], color="gray", alpha=0.4, linewidth=1)
    ax1.plot(prices["Date"], prices["LowerBand"], color="gray", alpha=0.4, linewidth=1)
    ax1.fill_between(prices["Date"], prices["LowerBand"], prices["UpperBand"], color="gray", alpha=0.08)

    # -----------------------------
    # Signal markers
    # -----------------------------
    lastK = np.nan
    lastD = np.nan
    lastLow = np.nan
    lastClose = np.nan
    lastLowBB = np.nan

    for i in prices.index:
        curK = prices.loc[i, "K"]
        curD = prices.loc[i, "D"]
        curLow = prices.loc[i, "Low"]
        curClose = prices.loc[i, close_col]
        curLowBB = prices.loc[i, "LowerBand"]
        curHigh = prices.loc[i, "High"]
        curDate = prices.loc[i, "Date"]

        # Green dot: K crosses above D under 60
        if pd.notna(lastK) and pd.notna(lastD) and pd.notna(curK) and pd.notna(curD):
            if curK > curD and lastK < lastD and lastK < 60:
                ax1.plot(curDate, curHigh * 1.01, marker="D", ms=4, ls="", color="green")

        # Red dot: lower Bollinger bounce
        if pd.notna(lastLow) and pd.notna(lastLowBB) and pd.notna(lastClose) and pd.notna(curLowBB):
            if ((lastLow < lastLowBB) or (curLow < curLowBB)) and (curClose > lastClose and curClose > curLowBB):
                if pd.notna(lastK) and lastK < 60:
                    ax1.plot(curDate, curLow * 0.99, marker="D", ms=4, ls="", color="red")

        lastK = curK
        lastD = curD
        lastLow = curLow
        lastClose = curClose
        lastLowBB = curLowBB

    # -----------------------------
    # Pivot points
    # -----------------------------
    pivots = []
    dates = []
    counter = 0
    Range = [0] * 10
    dateRange = [None] * 10

    for i in prices.index:
        currentMax = max(Range)
        value = round(float(prices.loc[i, "High"]), 2)

        Range = Range[1:] + [value]
        dateRange = dateRange[1:] + [i]

        if currentMax == max(Range):
            counter += 1
        else:
            counter = 0

        if counter == 5:
            lastPivot = currentMax
            dateloc = Range.index(lastPivot)
            lastDate = dateRange[dateloc]

            if lastDate is not None:
                pivots.append(lastPivot)
                dates.append(lastDate)

    timeD = dt.timedelta(days=30)

    for idx in range(len(pivots)):
        ax1.plot_date(
            [dates[idx] - (timeD * 0.075), dates[idx] + timeD],
            [pivots[idx], pivots[idx]],
            linestyle="--",
            linewidth=1,
            marker=",",
            color="black",
            alpha=0.6
        )
        ax1.annotate(
            str(pivots[idx]),
            (mdates.date2num(dates[idx]), pivots[idx]),
            xytext=(-10, 7),
            textcoords="offset points",
            fontsize=7,
            arrowprops=dict(arrowstyle='-|>')
        )

    # -----------------------------
    # Stochastic subplot
    # -----------------------------
    ax2.plot(prices["Date"], prices["K"], label="%K", linewidth=1.2)
    ax2.plot(prices["Date"], prices["D"], label="%D", linewidth=1.2)
    ax2.axhline(80, linestyle="--", alpha=0.5)
    ax2.axhline(20, linestyle="--", alpha=0.5)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Stochastic")
    ax2.legend()

    # -----------------------------
    # Formatting
    # -----------------------------
    ax1.set_title(f"{stock.upper()} - Daily")
    ax1.set_ylabel("Price")
    ax1.grid(True, linestyle="--", alpha=0.3)
    ax2.grid(True, linestyle="--", alpha=0.3)

    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax2.get_xticklabels(), rotation=45)

    ax1.legend()
    plt.tight_layout()
    plt.show()

    stock = input("Enter the ticker Symbol : ")