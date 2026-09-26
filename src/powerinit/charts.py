"""Charts for the initiation report (PNG, 200 dpi)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import BASE_FY, COVERAGE, OUTPUTS, PROCESSED, UNIVERSE, fy_label  # noqa: E402
from .forecast import load, project, sensitivity, target_price  # noqa: E402

CH = OUTPUTS / "charts"
INK, MUTED, GRID = "#1B2A3A", "#6B7785", "#E3E7EC"
ACCENT, ACCENT2, WARN = "#1F5F9E", "#7FA7CF", "#B5532A"
COVER_COL = {"NTPC": "#1F5F9E", "TATAPOWER": "#2E8B6E", "JSWENERGY": "#B5532A"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
})


def _save(fig, name):
    CH.mkdir(parents=True, exist_ok=True)
    p = CH / f"{name}.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return p


def sector_capex():
    f = pd.read_csv(PROCESSED / "fundamentals.csv")
    f = f[f.fy >= BASE_FY - 8].sort_values(["ticker", "fy"])
    f["capex"] = f.groupby("ticker").fixed_assets.diff() + f.depreciation + f.groupby("ticker").cwip.diff()
    f = f[f.fy >= BASE_FY - 7]
    piv = f.pivot_table(index="fy", columns="ticker", values="capex", aggfunc="sum").fillna(0)
    other = piv.drop(columns=list(COVERAGE)).sum(axis=1)
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    x = [fy_label(y) for y in piv.index]
    bottom = np.zeros(len(piv))
    for t in COVERAGE:
        ax.bar(x, piv[t] / 1e3, bottom=bottom, color=COVER_COL[t], label=UNIVERSE[t][0], width=0.62)
        bottom += piv[t].values / 1e3
    ax.bar(x, other / 1e3, bottom=bottom, color=GRID, label="Other listed peers", width=0.62)
    ax.set_ylabel("Rs '000 crore")
    ax.set_title("Listed power capex has more than doubled since FY23")
    ax.legend(frameon=False, ncol=4, fontsize=7.5, loc="upper left")
    return _save(fig, "sector_capex")


def comps_scatter():
    c = pd.read_csv(PROCESSED / "comps.csv", index_col=0)
    c = c[c.ev_ebitda.between(0, 40)]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for t, r in c.iterrows():
        col = COVER_COL.get(t, MUTED)
        ax.scatter(r.ebitda_margin * 100, r.ev_ebitda, s=np.sqrt(r.mcap_cr) / 3, color=col,
                   alpha=0.9 if t in COVERAGE else 0.55, edgecolor="white", linewidth=0.6)
        nudge = {"JPPOWER": (5, -8), "RPOWER": (5, -9), "TORNTPOWER": (-58, 4), "CESC": (-26, 4)}.get(t, (5, 2))
        ax.annotate(r["name"].replace(" Ltd", ""), (r.ebitda_margin * 100, r.ev_ebitda), fontsize=6.8,
                    xytext=nudge, textcoords="offset points", color=INK if t in COVERAGE else MUTED)
    ax.set_xlabel("EBITDA margin FY26A (%)")
    ax.set_ylabel("EV / EBITDA FY26A (x)")
    ax.set_title("Valuation vs margin: renewables and hydro command the premium (bubble = market cap)")
    return _save(fig, "comps_scatter")


def carbon_intensity():
    e = pd.read_csv(PROCESSED / "esg.csv")
    e = e[e.unit_flag == 0].sort_values("fy").groupby("ticker").tail(1)
    e = e[e.ticker.isin(pd.read_csv(PROCESSED / "comps.csv").ticker)].sort_values("carbon_intensity")
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    cols = [COVER_COL.get(t, ACCENT2) for t in e.ticker]
    ax.barh([UNIVERSE[t][0] for t in e.ticker], e.carbon_intensity, color=cols, height=0.62)
    for i, (v, fy) in enumerate(zip(e.carbon_intensity, e.fy)):
        ax.text(v, i, f" {v:,.0f}  ({fy_label(int(fy))})", va="center", fontsize=6.8, color=MUTED)
    ax.set_xlabel("Scope 1+2 tCO2e per Rs crore of revenue (BRSR, latest clean year)")
    ax.set_title("Carbon intensity: thermal-heavy generators sit 300x above hydro and RE")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, e.carbon_intensity.max() * 1.35)
    return _save(fig, "carbon_intensity")


def transcript_themes(ticker):
    t = pd.read_csv(PROCESSED / "transcript_themes.csv")
    t = t[(t.ticker == ticker) & (t.words > 1000)].sort_values("date")
    keys = ["thermal", "renewables", "storage", "nuclear", "distribution", "rooftop", "transmission"]
    keys = [k for k in keys if t[k].sum() >= 8]
    share = t[keys].div(t.words, axis=0) * 1000
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    palette = [INK, "#2E8B6E", ACCENT, WARN, "#8C6BB1", "#C9A227", ACCENT2]
    for k, col in zip(keys, palette):
        ax.plot(t.call, share[k], marker="o", ms=3, lw=1.6, color=col, label=k)
    ax.set_ylabel("mentions per 1,000 words")
    ax.set_title("What management talks about: theme intensity across earnings calls")
    ax.legend(frameon=False, ncol=len(keys), fontsize=7, loc="upper left", bbox_to_anchor=(0, 1.0))
    ax.set_ylim(0, share.values.max() * 1.35)
    return _save(fig, f"{ticker}_themes")


def earnings(ticker):
    hist, _ = load(ticker)
    fc = project(ticker)
    yrs_h = list(range(BASE_FY - 4, BASE_FY + 1))
    e = list(hist.loc[yrs_h, "operating_profit"]) + list(fc.ebitda)
    p = list(hist.loc[yrs_h, "net_profit"]) + list(fc.pat)
    labels = [fy_label(y) for y in yrs_h] + [fy_label(y, True) for y in fc.index]
    nd = list(hist.loc[yrs_h, "borrowings"] / hist.loc[yrs_h, "operating_profit"]) + \
        list((fc.borrowings - fc.cash_build) / fc.ebitda)
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    x = np.arange(len(labels))
    col = COVER_COL[ticker]
    ax.bar(x - 0.2, np.array(e) / 1e3, 0.4, color=col, label="EBITDA")
    ax.bar(x + 0.2, np.array(p) / 1e3, 0.4, color=ACCENT2 if ticker != "NTPC" else "#9BB8D6", label="Net profit")
    ax.axvspan(len(yrs_h) - 0.5, len(labels) - 0.5, color="#F3F5F8", zorder=0)
    ax.set_xticks(x, labels, fontsize=7)
    ax.set_ylabel("Rs '000 crore")
    ax2 = ax.twinx()
    ax2.plot(x, nd, color=WARN, lw=1.6, marker="o", ms=3, label="Net debt / EBITDA (rhs)")
    ax2.set_ylabel("x", color=WARN)
    ax2.tick_params(axis="y", colors=WARN)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax2.set_ylim(0, max(nd) * 1.4)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=7.5, ncol=3, loc="upper left")
    ax.set_title("Earnings and leverage, FY22A-FY33E (shaded = forecast)")
    return _save(fig, f"{ticker}_earnings")


def football(ticker):
    tp = target_price(ticker)
    _, mkt = load(ticker)
    cons = pd.read_csv(PROCESSED / "consensus.csv")
    cons = cons[(cons.ticker == ticker) & (cons.metric == "consensus_tp")]
    s = sensitivity(ticker)
    bars = [("52-week trading range", mkt.low_52w, mkt.high_52w, MUTED),
            ("DCF (WACC +/-1%, g 4-6%)", s.values.min(), s.values.max(), COVER_COL[ticker]),
            ("Peer EV/EBITDA (+/-2x)", tp["relative"] * 0.85, tp["relative"] * 1.15, ACCENT2)]
    fig, ax = plt.subplots(figsize=(6.4, 1.9))
    for i, (lab, lo, hi, col) in enumerate(bars):
        ax.barh(i, hi - lo, left=lo, color=col, height=0.5, alpha=0.85)
        ax.text(hi, i, f"  {lo:,.0f} - {hi:,.0f}", va="center", fontsize=7, color=MUTED)
    ax.set_yticks(range(len(bars)), [b[0] for b in bars])
    ax.axvline(mkt.price, color=INK, lw=1.2, ls="--")
    ax.text(mkt.price, len(bars) - 0.45, f"CMP {mkt.price:,.0f}", fontsize=7, color=INK, ha="center")
    ax.axvline(tp["tp"], color=WARN, lw=1.6)
    ax.text(tp["tp"], -0.75, f"TP {tp['tp']:,.0f}", fontsize=7.5, color=WARN, ha="center", weight="bold")
    for v in cons.value:
        ax.axvline(float(v), color="#2E8B6E", lw=1, ls=":")
    if len(cons):
        ax.text(float(cons.value.iloc[0]), len(bars) - 0.45, "consensus", fontsize=6.5, color="#2E8B6E", ha="left")
    ax.invert_yaxis()
    ax.set_ylim(len(bars) - 0.3, -1.0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Rs per share")
    ax.set_title("Valuation range")
    return _save(fig, f"{ticker}_football")


def all_charts():
    paths = [sector_capex(), comps_scatter(), carbon_intensity()]
    for t in COVERAGE:
        paths += [earnings(t), football(t), transcript_themes(t)]
    return paths


if __name__ == "__main__":
    for p in all_charts():
        print(p)
