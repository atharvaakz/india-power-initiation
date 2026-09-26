"""Three-statement forecast, DCF and target prices (reference implementation, model v2).

model_excel.py writes the same logic as live Excel formulas; tests/test_model.py
recalculates each workbook and checks it against this module.

Units: Rs crore unless stated. Balance sheet (Screener layout plus two forecast lines):
  Liabilities = equity capital + reserves + minority interest + borrowings + revolver + other liabilities
  Assets      = net block + CWIP + investments + other assets + incremental cash
Cash never goes below MARKET["min_cash"]: shortfalls draw a revolver, surpluses repay it first.
Revolver interest is charged on the opening balance, which keeps the model free of circularity.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .assumptions import COMPANIES, MARKET
from .config import BASE_FY, N_FORECAST, PROCESSED

KWH_FACTOR = 0.876     # MW x CUF x 8,760 h x Rs/kWh -> Rs crore:  x 8760 x 1000 / 1e7


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


def base_state(ticker: str) -> dict:
    """FY26A opening values, including the calibration of the two EBITDA engines."""
    a = COMPANIES[ticker]
    hist, mkt = load(ticker)
    b = hist.loc[BASE_FY]
    transfer0 = b.fixed_assets - hist.loc[BASE_FY - 1].fixed_assets + b.depreciation
    mw_prev = a["re_mw_prev"]
    mw0 = a["re_mw0"] if a["re_mw0"] is not None else a["re_share"] * transfer0 / a["re_cost"]
    re_rev0 = (mw_prev + mw0) / 2 * a["re_cuf"] * KWH_FACTOR * a["re_tariff"]
    re_ebitda0 = re_rev0 * a["re_margin"]
    core0 = b.operating_profit - re_ebitda0
    mi0 = float(mkt.minority_cr)
    s = dict(sales=b.sales, core=core0, core_margin=core0 / (b.sales - re_rev0), re_rev=re_rev0,
             re_ebitda=re_ebitda0, mw=mw0, nonre_transfer=transfer0 * (1 - a["re_share"]),
             transfer=transfer0, fa=b.fixed_assets, cwip=b.cwip, debt=b.borrowings, revolver=0.0,
             inv=b.investments, res=b.reserves, mi=mi0, ol=b.other_liabilities - mi0,
             cash=0.0, eqc=b.equity_capital, ebitda=b.operating_profit, pat=b.net_profit, jv=a["jv_profit0"])
    # other assets absorb the source's rounding so the opening balance sheet balances exactly
    s["oa"] = b.equity_capital + b.reserves + b.borrowings + b.other_liabilities - b.fixed_assets - b.cwip - b.investments
    s["mi_share"] = mi0 / (b.equity_capital + b.reserves + mi0)
    s["core0"] = core0
    if a["regulated"]:
        s["regeq"] = a["regeq0"]
        s["regeq_avg0"] = (a["regeq_prev"] + a["regeq0"]) / 2
    return s


def project(ticker: str) -> pd.DataFrame:
    a = COMPANIES[ticker]
    p = base_state(ticker)
    t_rate = MARKET["tax"]
    rows = []
    for i, y in enumerate(range(BASE_FY + 1, BASE_FY + 1 + N_FORECAST)):
        capex = a["capex_guided"][i] * a["execution"]
        transfer = (p["cwip"] + capex) * a["capitalisation"]
        re_transfer = transfer * a["re_share"]
        nonre_transfer = transfer - re_transfer
        mw = p["mw"] + re_transfer / a["re_cost"]
        re_rev = (p["mw"] + mw) / 2 * a["re_cuf"] * KWH_FACTOR * a["re_tariff"]
        re_ebitda = re_rev * a["re_margin"]
        if a["regulated"]:
            regeq = p["regeq"] + a["reg_equity_share"] * nonre_transfer
            # regulated EBITDA scales with the average regulated equity (all tariff components do)
            core = p["core0"] * (p["regeq"] + regeq) / 2 / p["regeq_avg0"]
        else:
            regeq = np.nan
            # half of last year's and half of this year's non-RE commissioning earns in the year
            core = p["core"] * (1 + a["base_drift"]) + a["asset_yield"] * 0.5 * (p["nonre_transfer"] + nonre_transfer)
        ebitda = core + re_ebitda
        sales = core / p["core_margin"] + re_rev
        oi = sales * a["other_income_pct"]
        dep = p["fa"] * a["dep_rate"]
        fa = p["fa"] + transfer - dep
        cwip = p["cwip"] + capex - transfer
        new_debt = capex * a["debt_share"]
        debt = p["debt"] + new_debt
        interest = (p["debt"] + debt) / 2 * a["int_rate"] + p["revolver"] * a["int_rate"]
        pbt = ebitda + oi - dep - interest
        tax = max(pbt, 0) * t_rate
        jv = p["jv"] * (1 + a["jv_growth"])
        mi_pat = (pbt - tax) * p["mi_share"]          # minorities share subsidiaries' profit, not JV profit
        pat = pbt - tax + jv
        pat_attr = pat - mi_pat
        div = max(pat_attr, 0) * a["payout"]
        res = p["res"] + pat_attr - div
        mi = p["mi"] + mi_pat
        inv_cash = p["inv"] * a["inv_growth"]          # new investments paid in cash
        inv = p["inv"] + inv_cash + jv                 # JV profit is retained in the investment (non-cash)
        oa = sales * a["oa_pct"]
        ol = sales * a["ol_pct"]
        d_nwc = (oa - ol) - (p["oa"] - p["ol"])
        cfo = pat - jv + dep - d_nwc
        cfi = -capex - inv_cash
        cff_pre = new_debt - div
        pre_cash = p["cash"] + cfo + cfi + cff_pre
        draw = max(MARKET["min_cash"] - pre_cash, -p["revolver"])
        revolver = p["revolver"] + draw
        cash = pre_cash + draw
        assets = fa + cwip + inv + oa + cash
        liabs = p["eqc"] + res + mi + debt + revolver + ol
        rows.append(dict(fy=y, sales=sales, core_ebitda=core, re_ebitda=re_ebitda, re_revenue=re_rev,
                         re_mw=mw, regulated_equity=regeq, ebitda=ebitda, other_income=oi, depreciation=dep,
                         interest=interest, pbt=pbt, tax=tax, jv_profit=jv, pat=pat, minority_pat=mi_pat,
                         pat_attr=pat_attr,
                         dividends=div, capex=capex, transfer=transfer, fixed_assets=fa, cwip=cwip,
                         investments=inv, other_assets=oa, cash=cash, borrowings=debt, revolver=revolver,
                         revolver_draw=draw, reserves=res, minority=mi, equity_capital=p["eqc"],
                         other_liabilities=ol, total_assets=assets, total_liabilities=liabs, d_nwc=d_nwc,
                         cfo=cfo, cfi=cfi, cff=cff_pre + draw))
        p.update(sales=sales, core=core, mw=mw, jv=jv, nonre_transfer=nonre_transfer, transfer=transfer, fa=fa,
                 cwip=cwip, debt=debt, revolver=revolver, inv=inv, res=res, mi=mi, oa=oa, ol=ol, cash=cash)
        if a["regulated"]:
            p["regeq"] = regeq
    fc = pd.DataFrame(rows).set_index("fy")
    fc["check"] = fc.total_assets - fc.total_liabilities
    assert fc.check.abs().max() < 1e-6, "balance sheet does not balance"
    assert (fc.cash >= MARKET["min_cash"] - 1e-9).all()
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
    """Equity value per share today."""
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
    # value-driver terminal value: reinvestment consistent with growth g at return RONIC
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


def dcf_12m(ticker: str) -> float:
    """DCF value rolled forward one year: grows at Ke, less the FY27 dividend paid out."""
    v = dcf(ticker)
    fc = project(ticker)
    _, mkt = load(ticker)
    return v.per_share * (1 + v.ke) - fc.dividends.iloc[0] / mkt.shares_cr


def relative_value(ticker: str) -> dict:
    """Peer-median EV/EBITDA (FY26A, the trailing year a year from now) on FY27E EBITDA,
    less FY27E net debt and minorities: a 12-month value."""
    from .comps import peer_multiple
    _, mkt = load(ticker)
    f = project(ticker).iloc[0]
    mult = peer_multiple(ticker)
    ev = mult * f.ebitda
    equity = ev - f.borrowings - f.revolver + mkt.cash_cr + f.cash - f.minority
    return dict(multiple=mult, ev=ev, per_share=equity / mkt.shares_cr)


def regulated_value(ticker: str, roe: float | None = None) -> dict:
    """Residual-income value of regulated equity at Mar-27 (FY27E):
    B_27 + sum_{t=28..36} (RoE - Ke) B_{t-1} / (1+Ke)^(t-27) + (RoE - Ke) B_36 / (Ke - g) / (1+Ke)^9."""
    a = COMPANIES[ticker]
    roe = a["roe"] if roe is None else roe
    ke = wacc_inputs(ticker)["ke"]
    g = a["pb_growth"]
    B = project(ticker).regulated_equity.values             # FY27E .. FY36E
    n = len(B) - 1
    ri = (roe - ke) * B[:-1] / (1 + ke) ** np.arange(1, n + 1)
    tv = (roe - ke) * B[-1] / (ke - g) / (1 + ke) ** n
    value = B[0] + ri.sum() + tv
    return {"value": value, "book": B[0], "pb": value / B[0], "roe": roe, "ke": ke}


def sotp(ticker: str, roe: float | None = None) -> dict:
    """NTPC at Mar-27: regulated equity by residual income + equity in regulated CWIP at book
    + listed NGEL stake at market less a holding-company discount."""
    a = COMPANIES[ticker]
    _, mkt = load(ticker)
    f = project(ticker).iloc[0]
    rv = regulated_value(ticker, roe)
    parts = {
        "Regulated equity (residual income)": rv["value"],
        "Equity in regulated CWIP at book": a["reg_equity_share"] * (1 - a["re_share"]) * f.cwip,
        "NGEL stake at market less holdco discount": a["ngel_stake"] * mkt.listed_sub_mcap_cr * (1 - MARKET["holdco_discount"]),
    }
    total = sum(parts.values())
    return {"pb": rv["pb"], "parts": parts, "equity": total, "per_share": total / mkt.shares_cr}


def implied_roe(ticker: str) -> float:
    """The earned RoE on regulated equity at which the SOTP equals today's price."""
    from scipy.optimize import brentq
    price = load(ticker)[1].price
    return brentq(lambda r: sotp(ticker, r)["per_share"] - price, 0.05, 0.40)


def target_price(ticker: str) -> dict:
    a = COMPANIES[ticker]
    v = dcf(ticker)
    r = relative_value(ticker)
    d12 = dcf_12m(ticker)
    if a["regulated"]:
        s = sotp(ticker)
        tp, method = s["per_share"], "SOTP"
    else:
        w = MARKET["dcf_weight"]
        tp, method = w * d12 + (1 - w) * r["per_share"], "50% DCF + 50% EV/EBITDA"
    up = tp / v.price - 1
    return dict(dcf=v.per_share, dcf_12m=d12, relative=r["per_share"], multiple=r["multiple"], tp=tp,
                method=method, price=v.price, upside=up, rating=rating(up), wacc=v.wacc, tv_share=v.tv_share)


def implied_wacc(ticker: str) -> float:
    """Reverse DCF: the WACC at which today's DCF value equals today's price."""
    from scipy.optimize import brentq
    price = dcf(ticker).price
    return brentq(lambda w: dcf(ticker, wacc=w).per_share - price, 0.055, 0.25)


def rating(upside: float) -> str:
    return "BUY" if upside > 0.15 else "SELL" if upside < -0.10 else "HOLD"


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    for t in COMPANIES:
        tp = target_price(t)
        fc = project(t)
        print(t, {k: round(v, 3) if isinstance(v, float) else v for k, v in tp.items()},
              f"implied WACC {implied_wacc(t):.2%}")
        if COMPANIES[t]["regulated"]:
            print("  SOTP", {k: round(v) for k, v in sotp(t)["parts"].items()}, "P/B", round(sotp(t)["pb"], 2),
                  "implied RoE", round(implied_roe(t), 4))
        print(fc[["sales", "core_ebitda", "re_ebitda", "ebitda", "re_mw", "regulated_equity", "pat_attr", "capex",
                  "borrowings", "revolver", "cash", "jv_profit"]].round(0).T.to_string())
