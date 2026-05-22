import io
import math
from datetime import datetime

try:
    import mplfinance as mpf
    import pandas as pd
    HAS_MPF = True
except ImportError:
    HAS_MPF = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _compute_ema(data, period):
    if len(data) < period:
        return [None] * len(data)
    result = []
    multiplier = 2 / (period + 1)
    ema = sum(data[:period]) / period
    result = [None] * (period - 1) + [ema]
    for i in range(period, len(data)):
        ema = (data[i] - ema) * multiplier + ema
        result.append(ema)
    return result


def generate_chart(bars, signal=None):
    if HAS_MPF:
        return _generate_mpf(bars, signal)
    if HAS_MPL:
        return _generate_mpl(bars, signal)
    return _empty_chart()


def _generate_mpf(bars, signal=None):
    df = _bars_to_dataframe(bars)
    if df.empty:
        return _empty_chart()

    style = mpf.make_mpf_style(
        base_mpf_style="charles",
        facecolor="#1a1a2e",
        figcolor="#1a1a2e",
        edgecolor="#2d2d44",
        gridcolor="#2d2d44",
        gridstyle=":",
        y_on_right=True,
        rc={
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.labelcolor": "#888888",
            "axes.edgecolor": "#2d2d44",
            "xtick.color": "#888888",
            "ytick.color": "#888888",
        },
    )

    apds = []
    ema21 = _compute_in_series(df["close"], 21)
    ema55 = _compute_in_series(df["close"], 55)
    if ema21 is not None:
        apds.append(mpf.make_addplot(ema21, color="#00d4aa", width=0.8, label="EMA21"))
    if ema55 is not None:
        apds.append(mpf.make_addplot(ema55, color="#ff6b6b", width=0.8, label="EMA55"))

    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=apds,
        volume=True,
        volume_alpha=0.3,
        figsize=(10, 7),
        returnfig=True,
        xrotation=0,
        tight_layout=True,
    )

    ax_main = axes[0]
    ax_vol = axes[2]

    _add_signal_annotations_mpf(ax_main, df, signal)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _generate_mpl(bars, signal=None):
    df = _bars_to_dataframe(bars)
    if df.empty:
        return _empty_chart()

    dates = list(df.index)
    closes = list(df["close"])
    opens = list(df["open"])
    highs = list(df["high"])
    lows = list(df["low"])
    volumes = list(df["volume"])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    fig.patch.set_facecolor("#1a1a2e")

    for ax in (ax1, ax2):
        ax.set_facecolor("#1a1a2e")
        ax.tick_params(colors="#888888", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#2d2d44")

    width = 0.6
    for i in range(len(dates)):
        color = "#00d4aa" if closes[i] >= opens[i] else "#ff6b6b"
        ax1.plot(
            [dates[i], dates[i]],
            [lows[i], highs[i]],
            color=color,
            linewidth=0.8,
        )
        rect = plt.Rectangle(
            (mdates.date2num(dates[i]) - width / 2, min(opens[i], closes[i])),
            width,
            abs(closes[i] - opens[i]) or 0.01,
            facecolor=color,
            edgecolor=color,
            linewidth=0.5,
        )
        ax1.add_patch(rect)

    ema21 = _compute_ema(closes, 21)
    ema55 = _compute_ema(closes, 55)

    ema21_plot = [(dates[i], ema21[i]) for i in range(len(dates)) if ema21[i] is not None]
    ema55_plot = [(dates[i], ema55[i]) for i in range(len(dates)) if ema55[i] is not None]

    if ema21_plot:
        ax1.plot(
            [p[0] for p in ema21_plot],
            [p[1] for p in ema21_plot],
            color="#00d4aa",
            linewidth=0.8,
            label="EMA21",
        )
    if ema55_plot:
        ax1.plot(
            [p[0] for p in ema55_plot],
            [p[1] for p in ema55_plot],
            color="#ff6b6b",
            linewidth=0.8,
            label="EMA55",
        )

    vol_colors = ["#00d4aa" if closes[i] >= opens[i] else "#ff6b6b" for i in range(len(dates))]
    max_vol = max(volumes) if volumes else 1
    ax2.bar(dates, volumes, width=width * 0.8, color=vol_colors, alpha=0.3)
    ax2.set_ylabel("Volume", color="#888888", fontsize=8)

    _add_signal_annotations_mpl(ax1, dates, signal)

    ax1.legend(
        loc="upper left",
        facecolor="#1a1a2e",
        edgecolor="#2d2d44",
        labelcolor="#cccccc",
        fontsize=8,
    )
    ax1.set_ylabel("Price", color="#888888", fontsize=8)
    ax1.grid(True, color="#2d2d44", linestyle=":", linewidth=0.5)
    ax2.grid(True, color="#2d2d44", linestyle=":", linewidth=0.5)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    fig.autofmt_xdate()
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _add_signal_annotations_mpf(ax, df, signal):
    if signal is None:
        return

    last_date = df.index[-1]
    last_close = df["close"].iloc[-1]

    entry_low = signal.get("entry_low")
    entry_high = signal.get("entry_high")
    stop_loss = signal.get("stop_loss")
    exit_target = signal.get("exit_target")

    if entry_low is not None and entry_high is not None:
        ax.axhspan(entry_low, entry_high, alpha=0.12, color="#00d4aa", zorder=2)
        ax.axhline(entry_low, color="#00d4aa", linewidth=0.6, linestyle=":", alpha=0.5)
        ax.axhline(entry_high, color="#00d4aa", linewidth=0.6, linestyle=":", alpha=0.5)

    if stop_loss is not None:
        ax.axhline(stop_loss, color="#ff6b6b", linewidth=1.0, linestyle="--", alpha=0.7)
        ax.annotate(
            f"SL ${stop_loss:.2f}",
            xy=(last_date, stop_loss),
            xytext=(10, -10),
            textcoords="offset points",
            color="#ff6b6b",
            fontsize=7,
            alpha=0.8,
        )

    if exit_target is not None:
        ax.axhline(exit_target, color="#00d4aa", linewidth=1.0, linestyle="--", alpha=0.7)
        ax.annotate(
            f"TGT ${exit_target:.2f}",
            xy=(last_date, exit_target),
            xytext=(10, 5),
            textcoords="offset points",
            color="#00d4aa",
            fontsize=7,
            alpha=0.8,
        )


def _add_signal_annotations_mpl(ax, dates, signal):
    if signal is None:
        return

    last_date = dates[-1]

    entry_low = signal.get("entry_low")
    entry_high = signal.get("entry_high")
    stop_loss = signal.get("stop_loss")
    exit_target = signal.get("exit_target")

    if entry_low is not None and entry_high is not None:
        ax.axhspan(entry_low, entry_high, alpha=0.12, color="#00d4aa", zorder=2)
        ax.axhline(entry_low, color="#00d4aa", linewidth=0.6, linestyle=":", alpha=0.5)
        ax.axhline(entry_high, color="#00d4aa", linewidth=0.6, linestyle=":", alpha=0.5)

    if stop_loss is not None:
        ax.axhline(stop_loss, color="#ff6b6b", linewidth=1.0, linestyle="--", alpha=0.7)
        ax.annotate(
            f"SL ${stop_loss:.2f}",
            xy=(last_date, stop_loss),
            xytext=(10, -10),
            textcoords="offset points",
            color="#ff6b6b",
            fontsize=7,
            alpha=0.8,
        )

    if exit_target is not None:
        ax.axhline(exit_target, color="#00d4aa", linewidth=1.0, linestyle="--", alpha=0.7)
        ax.annotate(
            f"TGT ${exit_target:.2f}",
            xy=(last_date, exit_target),
            xytext=(10, 5),
            textcoords="offset points",
            color="#00d4aa",
            fontsize=7,
            alpha=0.8,
        )


def _compute_in_series(series, period):
    if len(series) < period:
        return None
    result = [None] * len(series)
    multiplier = 2 / (period + 1)
    ema = series.iloc[:period].mean()
    result[period - 1] = ema
    for i in range(period, len(series)):
        ema = (series.iloc[i] - ema) * multiplier + ema
        result[i] = ema
    return pd.Series(result, index=series.index)


def _bars_to_dataframe(bars):
    import pandas as pd

    records = []
    for b in bars:
        if isinstance(b, dict):
            ts = b.get("timestamp") or b.get("date") or b.get("time")
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            elif isinstance(ts, str):
                dt = datetime.fromisoformat(ts)
            else:
                dt = ts
            records.append(
                {
                    "date": dt,
                    "open": float(b["open"]),
                    "high": float(b["high"]),
                    "low": float(b["low"]),
                    "close": float(b["close"]),
                    "volume": float(b.get("volume", 0)),
                }
            )
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)
    df = df.tail(60)
    return df


def _empty_chart():
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    ax.text(
        0.5,
        0.5,
        "No chart data available",
        ha="center",
        va="center",
        color="#888888",
        fontsize=12,
        transform=ax.transAxes,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
