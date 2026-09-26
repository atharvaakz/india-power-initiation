"""Build the processed inputs every later stage reads.

fundamentals.csv  consolidated annual financials, Rs crore, FY14A-FY26A (Screener export)
market.csv        price, shares, cash, minority interest and beta as of the valuation date
esg.csv           scope 1+2 emissions and carbon intensity from BRSR filings, with unit flags

Only this module touches the raw research workspace or the network; everything
downstream runs off the processed CSVs, which are committed.
"""
import numpy as np
import pandas as pd

from .config import ASOF, BASE_FY, MASTER_PANEL, PROCESSED, SCREENER_DTA, UNIVERSE

CR = 1e7  # rupees per crore

FUND_COLS = ["sales", "expenses", "operating_profit", "other_income", "interest",
             "depreciation", "pbt", "net_profit", "equity_capital", "reserves",
             "borrowings", "other_liabilities", "total_liabilities", "fixed_assets",
             "cwip", "investments", "other_assets", "total_assets", "cfo", "cfi", "cff"]


def build_fundamentals() -> pd.DataFrame:
    sc = pd.read_stata(SCREENER_DTA)
    sc = sc[sc.nse_symbol.isin(UNIVERSE) & (sc.basis == "consolidated")]
    out = sc[["nse_symbol", "fy"] + FUND_COLS].sort_values(["nse_symbol", "fy"])
    out = out.rename(columns={"nse_symbol": "ticker"})
    # Screener's balance sheet is two-sided; a mismatch means a bad row.
    gap = (out.total_assets - out.total_liabilities).abs() / out.total_assets
    assert (gap.fillna(0) < 0.01).all(), out[gap >= 0.01]
    out.to_csv(PROCESSED / "fundamentals.csv", index=False)
    return out


def _beta(px: pd.Series, mkt: pd.Series) -> float:
    """2-year weekly beta against the Nifty 50."""
    r = pd.concat([px, mkt], axis=1).dropna().resample("W-FRI").last().pct_change().dropna()
    r = r.iloc[-104:]
    return float(np.cov(r.iloc[:, 0], r.iloc[:, 1])[0, 1] / r.iloc[:, 1].var())


def _pick(frame: pd.DataFrame, rows: list[str]) -> float:
    """First available balance-sheet line for the FY26 column, in Rs crore."""
    col = [c for c in frame.columns if c.year == BASE_FY + 1 and c.month == 3]
    if not col:
        return np.nan
    for r in rows:
        if r in frame.index and pd.notna(frame.loc[r, col[0]]):
            return float(frame.loc[r, col[0]]) / CR
    return 0.0


def build_market() -> pd.DataFrame:
    import yfinance as yf

    end = (pd.Timestamp(ASOF) + pd.Timedelta(days=1)).date().isoformat()
    start = (pd.Timestamp(ASOF) - pd.Timedelta(days=3 * 365)).date().isoformat()
    nifty = yf.Ticker("^NSEI").history(start=start, end=end)["Close"]
    nifty.index = nifty.index.tz_localize(None)
    rows = []
    for t in UNIVERSE:
        tk = yf.Ticker(f"{t}.NS")
        h = tk.history(start=start, end=end)["Close"]
        h.index = h.index.tz_localize(None)
        bs = tk.balance_sheet
        rows.append({
            "ticker": t,
            "price_date": h.index[-1].date().isoformat(),
            "price": round(float(h.iloc[-1]), 2),
            "shares_cr": tk.fast_info["shares"] / CR,
            "cash_cr": _pick(bs, ["Cash Cash Equivalents And Short Term Investments",
                                  "Cash And Cash Equivalents"]),
            "minority_cr": _pick(bs, ["Minority Interest"]),
            "beta_2y_weekly": round(_beta(h, nifty), 3),
            "high_52w": round(float(h.iloc[-252:].max()), 2),
            "low_52w": round(float(h.iloc[-252:].min()), 2),
        })
    mk = pd.DataFrame(rows)
    # Listed subsidiaries valued at market in the sum of the parts.
    ng = yf.Ticker("NTPCGREEN.NS")
    ngp = ng.history(start=start, end=end)["Close"]
    mk["listed_sub_mcap_cr"] = 0.0
    mk.loc[mk.ticker == "NTPC", "listed_sub_mcap_cr"] = float(ngp.iloc[-1]) * ng.fast_info["shares"] / CR
    mk["mcap_cr"] = mk.price * mk.shares_cr
    mk.to_csv(PROCESSED / "market.csv", index=False)
    return mk


def build_esg() -> pd.DataFrame:
    """Carbon intensity = scope 1+2 tCO2e per Rs crore of revenue.

    BRSR filers mix units (tonnes vs million tonnes vs kg). Rows are flagged,
    not rescaled: a thermal generator reporting under 50 t/Rs cr is a unit
    error, and so is any year more than 5x away from the firm's own median.
    """
    cols = ["nse_symbol", "fy", "scope1_emissions", "scope2_emissions", "scope12_emissions", "sales_sc"]
    mp = pd.read_csv(MASTER_PANEL, usecols=cols, low_memory=False)
    mp = mp[mp.nse_symbol.isin(UNIVERSE)].rename(columns={"nse_symbol": "ticker", "sales_sc": "sales_cr"})
    mp = mp.dropna(subset=["scope12_emissions", "sales_cr"]).sort_values(["ticker", "fy"])
    mp["carbon_intensity"] = mp.scope12_emissions / mp.sales_cr
    thermal = {"NTPC", "TATAPOWER", "JSWENERGY", "ADANIPOWER", "TORNTPOWER", "CESC",
               "NLCINDIA", "RPOWER", "JPPOWER"}
    bad_thermal = mp.ticker.isin(thermal) & (mp.carbon_intensity < 50)
    med = mp[~bad_thermal].groupby("ticker").carbon_intensity.median()
    rel = mp.carbon_intensity / mp.ticker.map(med)
    mp["unit_flag"] = (bad_thermal | (rel > 5) | (rel < 0.2)).astype(int)
    mp.to_csv(PROCESSED / "esg.csv", index=False)
    return mp


if __name__ == "__main__":
    PROCESSED.mkdir(parents=True, exist_ok=True)
    print(build_fundamentals().groupby("ticker").fy.agg(["min", "max"]))
    print(build_esg().query("unit_flag == 1")[["ticker", "fy", "carbon_intensity"]])
    print(build_market())
