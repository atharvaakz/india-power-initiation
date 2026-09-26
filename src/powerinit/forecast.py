"""Three-statement forecast and DCF, in Python.

This is the reference implementation of the model. model_excel.py writes the
same logic as live Excel formulas, and tests/test_model.py recomputes the
workbook to confirm both give the same target price.

Units: Rs crore unless stated. Balance sheet follows the Screener layout:
  Liabilities = equity capital + reserves + borrowings + other liabilities
  Assets      = net block + CWIP + investments + other assets (+ forecast cash build)
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .assumptions import COMPANIES, MARKET
from .config import BASE_FY, N_FORECAST, PROCESSED


@dataclass
class Valuation:
    wacc: float
    ke: float
    beta: float
    ev: float
    equity: float
    per_share: float
    price: float
    upside: float
    tv_share: float
    table: pd.DataFrame


def load(ticker: str):
    f = pd.read_csv(PROCESSED / "fundamentals.csv")
    m = pd.read_csv(PROCESSED / "market.csv").set_index("ticker").loc[ticker]
    return f[f.ticker == ticker].set_index("fy"), m


def project(ticker: str) -> pd.DataFrame:
    """Rows = line items, columns = fiscal years (history + forecast)."""
    a = COMPANIES[ticker]
    hist, mkt = load(ticker)
    b = hist.loc[BASE_FY]
    years = list(range(BASE_FY + 1, BASE_FY + 1 + N_FORECAST))
    # Other assets absorb the source's small base-year rounding gap so the opening balance sheet balances.
    oa0 = (b.equity_capital + b.reserves + b.borrowings + b.other_liabilities
           - b.fixed_assets - b.cwip - b.investments)
    transfer0 = b.fixed_assets - hist.loc[BASE_FY - 1].fixed_assets + b.depreciation
    rows = []
    prev = dict(sales=b.sales, ebitda=b.operating_profit, transfer=transfer0, fa=b.fixed_assets,
                cwip=b.cwip, debt=b.borrowings, inv=b.investments, res=b.reserves, oa=oa0,
                ol=b.other_liabilities, cash=0.0)
    for i, y in enumerate(years):
        capex = a["capex_guided"][i] * a["execution"]
        transfer = (prev["cwip"] + capex) * a["capitalisation"]
        # Assets commissioned mid-year: half of this year's and half of last year's earn in the year.
        ebitda = (prev["ebitda"] * (1 + a["base_drift"])
                  + a["asset_yield"] * 0.5 * (prev["transfer"] + transfer))
        sales = ebitda / a["ebitda_margin"][i]
        oi = sales * a["other_income_pct"]
        dep = prev["fa"] * a["dep_rate"]
        fa = prev["fa"] + transfer - dep
        cwip = prev["cwip"] + capex - transfer
        new_debt = capex * a["debt_share"]
        debt = prev["debt"] + new_debt
        interest = (prev["debt"] + debt) / 2 * a["int_rate"]
        pbt = ebitda + oi - dep - interest
        tax = max(pbt, 0) * MARKET["tax"]
        pat = pbt - tax
        div = max(pat, 0) * a["payout"]
        res = prev["res"] + pat - div
        inv = prev["inv"] * (1 + a["inv_growth"])
        oa = sales * a["oa_pct"]
        ol = sales * a["ol_pct"]
        d_nwc = (oa - ol) - (prev["oa"] - prev["ol"])
        cfo = pat + dep - d_nwc
        cfi = -capex - (inv - prev["inv"])
        cff = new_debt - div
        cash = prev["cash"] + cfo + cfi + cff
        assets = fa + cwip + inv + oa + cash
        liabs = b.equity_capital + res + debt + ol
        rows.append(dict(fy=y, sales=sales, ebitda=ebitda, other_income=oi, depreciation=dep,
                         interest=interest, pbt=pbt, tax=tax, pat=pat, dividends=div,
                         capex=capex, transfer=transfer, fixed_assets=fa, cwip=cwip,
                         investments=inv, other_assets=oa, cash_build=cash, borrowings=debt,
                         reserves=res, equity_capital=b.equity_capital, other_liabilities=ol,
                         total_assets=assets, total_liabilities=liabs, d_nwc=d_nwc,
                         cfo=cfo, cfi=cfi, cff=cff))
        prev = dict(sales=sales, ebitda=ebitda, transfer=transfer, fa=fa, cwip=cwip, debt=debt,
                    inv=inv, res=res, oa=oa, ol=ol, cash=cash)
    fc = pd.DataFrame(rows).set_index("fy")
    fc["check"] = fc.total_assets - fc.total_liabilities
    assert fc.check.abs().max() < 1e-6, "balance sheet does not balance"
    return fc


def wacc_inputs(ticker: str):
    a = COMPANIES[ticker]
    hist, mkt = load(ticker)
    rf = MARKET["gsec_10y"] - MARKET["default_spread"]
    beta = 0.67 * mkt.beta_2y_weekly + 0.33           # Blume-adjusted
    ke = rf + beta * MARKET["erp"]
    d = hist.loc[BASE_FY].borrowings
    e = mkt.mcap_cr
    wd = d / (d + e)
    wacc = (1 - wd) * ke + wd * a["kd"] * (1 - MARKET["tax"])
    return dict(rf=rf, beta=beta, ke=ke, kd=a["kd"], wd=wd, wacc=wacc, debt=d, mcap=e)


def dcf(ticker: str, wacc: float | None = None, g: float | None = None) -> Valuation:
    a = COMPANIES[ticker]
    hist, mkt = load(ticker)
    fc = project(ticker)
    w = wacc_inputs(ticker)
    wacc = w["wacc"] if wacc is None else wacc
    g = a["g"] if g is None else g
    t = MARKET["tax"]
    nopat = (fc.ebitda - fc.depreciation) * (1 - t)
    fcff = nopat + fc.depreciation - fc.capex - fc.d_nwc
    stub = MARKET["stub"]
    fcff.iloc[0] *= stub                               # only the unexpired part of FY27
    period = stub + np.arange(len(fc))
    pv = fcff / (1 + wacc) ** period
    # Value-driver terminal value: reinvestment consistent with growth g at return RONIC.
    tv = nopat.iloc[-1] * (1 + g) * (1 - g / a["ronic"]) / (wacc - g)
    pv_tv = tv / (1 + wacc) ** period[-1]
    ev = pv.sum() + pv_tv
    b = hist.loc[BASE_FY]
    equity = ev - b.borrowings + mkt.cash_cr + b.investments - mkt.minority_cr
    ps = equity / mkt.shares_cr
    table = pd.DataFrame({"nopat": nopat, "fcff": fcff, "period": period, "pv": pv})
    return Valuation(wacc=wacc, ke=w["ke"], beta=w["beta"], ev=ev, equity=equity, per_share=ps,
                     price=mkt.price, upside=ps / mkt.price - 1, tv_share=pv_tv / ev, table=table)


def sensitivity(ticker: str, waccs=None, gs=None) -> pd.DataFrame:
    base = dcf(ticker)
    waccs = waccs or [base.wacc + d for d in (-0.01, -0.005, 0, 0.005, 0.01)]
    gs = gs or [0.04, 0.045, 0.05, 0.055, 0.06]
    return pd.DataFrame([[dcf(ticker, w, g).per_share for g in gs] for w in waccs],
                        index=[f"{w:.1%}" for w in waccs], columns=[f"{g:.1%}" for g in gs])


def relative_value(ticker: str) -> dict:
    """Equity value per share at the peer-median FY26A EV/EBITDA."""
    from .comps import peer_multiple
    hist, mkt = load(ticker)
    b = hist.loc[BASE_FY]
    mult = peer_multiple(ticker)
    ev = mult * b.operating_profit
    equity = ev - b.borrowings + mkt.cash_cr - mkt.minority_cr
    return dict(multiple=mult, ev=ev, per_share=equity / mkt.shares_cr)


def target_price(ticker: str) -> dict:
    v = dcf(ticker)
    r = relative_value(ticker)
    w = MARKET["dcf_weight"]
    tp = w * v.per_share + (1 - w) * r["per_share"]
    up = tp / v.price - 1
    return dict(dcf=v.per_share, relative=r["per_share"], multiple=r["multiple"], tp=tp,
                price=v.price, upside=up, rating=rating(up), wacc=v.wacc, tv_share=v.tv_share)


def implied_wacc(ticker: str) -> float:
    """Reverse DCF: the WACC at which the DCF equals today's price."""
    from scipy.optimize import brentq
    price = dcf(ticker).price
    return brentq(lambda w: dcf(ticker, wacc=w).per_share - price, 0.055, 0.25)


def rating(upside: float) -> str:
    return "BUY" if upside > 0.15 else "SELL" if upside < -0.10 else "HOLD"


if __name__ == "__main__":
    for t in COMPANIES:
        tp = target_price(t)
        fc = project(t)
        print(t, {k: round(v, 3) if isinstance(v, float) else v for k, v in tp.items()},
              f"implied WACC {implied_wacc(t):.2%}")
        print(fc[["sales", "ebitda", "pat", "capex", "borrowings", "cash_build"]].round(0).T.to_string())
