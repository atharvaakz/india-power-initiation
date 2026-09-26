"""Write each covered company's model as an Excel workbook with live formulas.

Sheets: Cover | Inputs | Model (IS/BS/CF, FY22A-FY33E) | DCF (WACC, FCFF, TV,
bridge, blended target, sensitivity) | Comps | Guidance.
Blue cells are inputs; black cells are formulas. Change an input and the target
price moves. Logic mirrors forecast.py line for line.
"""
import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell

from .assumptions import COMPANIES, MARKET
from .comps import PEER_SETS, peer_multiple
from .config import BASE_FY, COVERAGE, N_FORECAST, OUTPUTS, PROCESSED, fy_label
from .forecast import load

HIST_YEARS = list(range(BASE_FY - 4, BASE_FY + 1))            # FY22A..FY26A
FC_YEARS = list(range(BASE_FY + 1, BASE_FY + 1 + N_FORECAST))  # FY27E..FY33E
FIRST_COL = 2                                                   # column C
COL = {y: FIRST_COL + i for i, y in enumerate(HIST_YEARS + FC_YEARS)}
L = {y: xl_col_to_name(c) for y, c in COL.items()}


class Book:
    def __init__(self, path):
        self.wb = xlsxwriter.Workbook(path)
        f = self.wb.add_format
        base = {"font_name": "Arial", "font_size": 9}
        self.fmt = {
            "title": f({**base, "bold": True, "font_size": 13}),
            "h": f({**base, "bold": True, "bottom": 1}),
            "sec": f({**base, "bold": True, "bg_color": "#E8EEF4"}),
            "lbl": f(base),
            "num": f({**base, "num_format": "#,##0;(#,##0)"}),
            "num_b": f({**base, "num_format": "#,##0;(#,##0)", "bold": True, "top": 1}),
            "pct": f({**base, "num_format": "0.0%"}),
            "x": f({**base, "num_format": "0.0x"}),
            "dec": f({**base, "num_format": "0.00"}),
            "in_num": f({**base, "num_format": "#,##0", "font_color": "#1F4E9E"}),
            "in_pct": f({**base, "num_format": "0.0%", "font_color": "#1F4E9E"}),
            "in_dec": f({**base, "num_format": "0.000", "font_color": "#1F4E9E"}),
            "in_txt": f({**base, "font_color": "#1F4E9E"}),
            "chk": f({**base, "num_format": "0.00;-0.00;\"OK\"", "font_color": "#2E7D32"}),
            "big": f({**base, "bold": True, "font_size": 12, "num_format": "#,##0"}),
            "wrap": f({**base, "text_wrap": True, "valign": "top"}),
            "note": f({**base, "italic": True, "font_color": "#666666"}),
        }

    def sheet(self, name, widths=None):
        ws = self.wb.add_worksheet(name)
        ws.set_column(0, 0, 34)
        ws.set_column(1, 1, 8)
        ws.set_column(2, 16, 11)
        for c, w in (widths or {}).items():
            ws.set_column(c, c, w)
        ws.hide_gridlines(2)
        return ws


def build(ticker: str) -> str:
    a = COMPANIES[ticker]
    hist, mkt = load(ticker)
    OUTPUTS.mkdir(exist_ok=True)
    path = OUTPUTS / f"{ticker}_model.xlsx"
    bk = Book(str(path))
    F = bk.fmt
    wb = bk.wb

    # ------------------------------------------------------------------ Inputs
    inp = bk.sheet("Inputs", {2: 14, 3: 70})
    inp.write(0, 0, f"{COVERAGE[ticker]} - inputs (Rs crore)", F["title"])
    scalars = [
        ("gsec", "India 10Y G-sec yield", MARKET["gsec_10y"], "in_pct", "Trading Economics, 25-Sep-2026"),
        ("ds", "Sovereign default spread", MARKET["default_spread"], "in_pct", "Damodaran, Jan-2026 (Baa3)"),
        ("erp", "Equity risk premium (India, total)", MARKET["erp"], "in_pct", "Damodaran, Jan-2026"),
        ("tax", "Tax rate", MARKET["tax"], "in_pct", "New corporate regime, 25.17% rounded"),
        ("stub", "FY27 fraction remaining", MARKET["stub"], "in_dec", "Valuation date 25-Sep-2026"),
        ("w_dcf", "Weight on DCF in target", MARKET["dcf_weight"], "in_pct", "Balance on peer EV/EBITDA"),
        ("beta_raw", "Raw beta (2y weekly vs Nifty 50)", mkt.beta_2y_weekly, "in_dec", "Computed from NSE prices"),
        ("kd", "Pre-tax cost of debt", a["kd"], "in_pct", a["rf_spread_note"]),
        ("g", "Terminal growth", a["g"], "in_pct", "Nominal INR"),
        ("ronic", "Return on new invested capital (terminal)", a["ronic"], "in_pct", a["rationale"]["terminal"]),
        ("price", "Share price (Rs)", mkt.price, "in_num", f"NSE close {mkt.price_date}"),
        ("shares", "Shares outstanding (crore)", mkt.shares_cr, "in_dec", "NSE / yfinance"),
        ("cash", "Cash & short-term investments FY26", mkt.cash_cr, "in_num", "FY26 balance sheet"),
        ("mi", "Minority interest FY26", mkt.minority_cr, "in_num", "FY26 balance sheet"),
        ("mult", "Peer median EV/EBITDA FY26A", peer_multiple(ticker), "x", "Peers: " + ", ".join(p for p in PEER_SETS[ticker] if p != ticker)),
        ("execution", "Capex execution vs guidance", a["execution"], "in_pct", a["rationale"]["capex"]),
        ("yield", "EBITDA yield on commissioned assets", a["asset_yield"], "in_pct", a["rationale"]["growth"]),
        ("drift", "EBITDA growth of existing assets", a["base_drift"], "in_pct", ""),
        ("oi", "Other income % of sales", a["other_income_pct"], "in_pct", ""),
        ("dep", "Depreciation % opening net block", a["dep_rate"], "in_pct", ""),
        ("capz", "Capitalisation % of (CWIP + capex)", a["capitalisation"], "in_pct", ""),
        ("debt_share", "New debt % of capex", a["debt_share"], "in_pct", ""),
        ("int", "Interest % average debt", a["int_rate"], "in_pct", ""),
        ("payout", "Dividend payout", a["payout"], "in_pct", "FY26 actual"),
        ("oa", "Other (non-cash) assets % of sales", a["oa_pct"], "in_pct", ""),
        ("ol", "Other liabilities % of sales", a["ol_pct"], "in_pct", ""),
        ("inv_g", "Investments growth", a["inv_growth"], "in_pct", ""),
    ]
    N = {}
    inp.write_row(2, 0, ["Input", "", "Value", "Source / rationale"], F["h"])
    for i, (key, label, val, fmt, src) in enumerate(scalars):
        r = 3 + i
        inp.write(r, 0, label, F["lbl"])
        inp.write(r, 2, val, F[fmt] if fmt != "x" else F["x"])
        inp.write(r, 3, src, F["note"])
        wb.define_name(f"in_{key}", f"=Inputs!$C${r + 1}")   # for readers; formulas use the address
        N[key] = f"Inputs!$C${r + 1}"

    # ------------------------------------------------------------------- Model
    ws = bk.sheet("Model")
    ws.freeze_panes(3, 2)
    ws.write(0, 0, f"{COVERAGE[ticker]} - consolidated model (Rs crore)", F["title"])
    for y in HIST_YEARS + FC_YEARS:
        ws.write(2, COL[y], fy_label(y, y > BASE_FY), F["h"])
    ws.write(2, 0, "", F["h"])
    ws.write(2, 1, "", F["h"])

    # Row positions are fixed up front because formulas refer forward and backward.
    layout = ["#Drivers", "capex_g", "margin",
              "#Income statement", "sales", "ebitda", "oi", "dep", "int", "pbt", "tax", "pat", "eps", "div",
              "#Balance sheet", "fa", "cwip", "inv", "oa", "cash", "ta", "eqc", "res", "debt", "ol", "tl", "check",
              "#Capex and commissioning", "capex", "transfer",
              "#Cash flow", "dnwc", "cfo", "cfi", "cff",
              "#Ratios", "nd_ebitda", "roe"]
    R = {k: 3 + i for i, k in enumerate(layout) if not k.startswith("#")}
    SEC = {k[1:]: 3 + i for i, k in enumerate(layout) if k.startswith("#")}

    def section(title):
        r = SEC[title]
        ws.write(r, 0, title, F["sec"])
        for c in range(1, COL[FC_YEARS[-1]] + 1):
            ws.write_blank(r, c, None, F["sec"])

    def line(key, label, hist_vals=None, fc=None, fmt="num", hist_formula=None, base_value=None):
        r = R[key]
        ws.write(r, 0, label, F["lbl"])
        for y in HIST_YEARS:
            if hist_formula:
                ws.write_formula(r, COL[y], hist_formula(y), F[fmt])
            elif hist_vals is not None:
                v = hist_vals.get(y)
                if v is not None and pd.notna(v):
                    ws.write(r, COL[y], float(v), F[fmt])
        if base_value is not None:
            ws.write(r, COL[BASE_FY], float(base_value), F[fmt])
        if fc:
            for i, y in enumerate(FC_YEARS):
                ws.write_formula(r, COL[y], "=" + fc(L[y], L[y - 1], i), F[fmt])

    def c(key, col):
        return f"{col}{R[key] + 1}"

    h = hist
    for title in SEC:
        section(title)
    ws.write(R["capex_g"], 0, "Capex guided (mgmt)", F["lbl"])
    for i, y in enumerate(FC_YEARS):
        ws.write(R["capex_g"], COL[y], a["capex_guided"][i], F["in_num"])
    ws.write(R["margin"], 0, "EBITDA margin", F["lbl"])
    for i, y in enumerate(FC_YEARS):
        ws.write(R["margin"], COL[y], a["ebitda_margin"][i], F["in_pct"])

    line("sales", "Revenue", h.sales.to_dict(), lambda x, p, i: f"{c('ebitda', x)}/{c('margin', x)}")
    line("ebitda", "EBITDA", h.operating_profit.to_dict(),
         lambda x, p, i: f"{c('ebitda', p)}*(1+{N['drift']})+{N['yield']}*0.5*({c('transfer', p)}+{c('transfer', x)})")
    for y in HIST_YEARS:
        ws.write_formula(R["margin"], COL[y], f"={c('ebitda', L[y])}/{c('sales', L[y])}", F["pct"])
    line("oi", "Other income", h.other_income.to_dict(), lambda x, p, i: f"{c('sales', x)}*{N['oi']}")
    line("dep", "Depreciation", h.depreciation.to_dict(), lambda x, p, i: f"{c('fa', p)}*{N['dep']}")
    line("int", "Interest", h.interest.to_dict(), lambda x, p, i: f"({c('debt', p)}+{c('debt', x)})/2*{N['int']}")
    line("pbt", "Profit before tax", h.pbt.to_dict(),
         lambda x, p, i: f"{c('ebitda', x)}+{c('oi', x)}-{c('dep', x)}-{c('int', x)}")
    line("tax", "Tax", (h.pbt - h.net_profit).to_dict(), lambda x, p, i: f"MAX({c('pbt', x)},0)*{N['tax']}")
    line("pat", "Net profit", h.net_profit.to_dict(), lambda x, p, i: f"{c('pbt', x)}-{c('tax', x)}")
    line("eps", "EPS (Rs)", fmt="dec", hist_formula=lambda y: f"={c('pat', L[y])}/{N['shares']}",
         fc=lambda x, p, i: f"{c('pat', x)}/{N['shares']}")
    line("div", "Dividends", fc=lambda x, p, i: f"MAX({c('pat', x)},0)*{N['payout']}")

    oa0 = h.loc[BASE_FY, ["equity_capital", "reserves", "borrowings", "other_liabilities"]].sum() - \
        h.loc[BASE_FY, ["fixed_assets", "cwip", "investments"]].sum()
    line("fa", "Net block", h.fixed_assets.to_dict(), lambda x, p, i: f"{c('fa', p)}+{c('transfer', x)}-{c('dep', x)}")
    line("cwip", "Capital work in progress", h.cwip.to_dict(),
         lambda x, p, i: f"{c('cwip', p)}+{c('capex', x)}-{c('transfer', x)}")
    line("inv", "Investments", h.investments.to_dict(), lambda x, p, i: f"{c('inv', p)}*(1+{N['inv_g']})")
    oa_hist = h.other_assets.to_dict()
    oa_hist[BASE_FY] = oa0
    line("oa", "Other assets (non-cash)", oa_hist, lambda x, p, i: f"{c('sales', x)}*{N['oa']}")
    line("cash", "Cash build from FY26", {BASE_FY: 0.0},
         lambda x, p, i: f"{c('cash', p)}+{c('cfo', x)}+{c('cfi', x)}+{c('cff', x)}")
    line("ta", "Total assets", fmt="num_b",
         hist_formula=lambda y: f"={c('fa', L[y])}+{c('cwip', L[y])}+{c('inv', L[y])}+{c('oa', L[y])}"
                                + (f"+{c('cash', L[y])}" if y == BASE_FY else ""),
         fc=lambda x, p, i: f"{c('fa', x)}+{c('cwip', x)}+{c('inv', x)}+{c('oa', x)}+{c('cash', x)}")
    line("eqc", "Equity capital", h.equity_capital.to_dict(), lambda x, p, i: c("eqc", p))
    line("res", "Reserves", h.reserves.to_dict(), lambda x, p, i: f"{c('res', p)}+{c('pat', x)}-{c('div', x)}")
    line("debt", "Borrowings", h.borrowings.to_dict(),
         lambda x, p, i: f"{c('debt', p)}+{c('capex', x)}*{N['debt_share']}")
    line("ol", "Other liabilities", h.other_liabilities.to_dict(), lambda x, p, i: f"{c('sales', x)}*{N['ol']}")
    line("tl", "Total liabilities & equity", fmt="num_b",
         hist_formula=lambda y: f"={c('eqc', L[y])}+{c('res', L[y])}+{c('debt', L[y])}+{c('ol', L[y])}",
         fc=lambda x, p, i: f"{c('eqc', x)}+{c('res', x)}+{c('debt', x)}+{c('ol', x)}")
    line("check", "Balance check (assets - liabilities)", fmt="chk",
         hist_formula=lambda y: f"=IF(ABS({c('ta', L[y])}-{c('tl', L[y])})<2,0,{c('ta', L[y])}-{c('tl', L[y])})",
         fc=lambda x, p, i: f"ROUND({c('ta', x)}-{c('tl', x)},4)")

    capex_hist = (h.fixed_assets.diff() + h.depreciation + h.cwip.diff()).to_dict()
    line("capex", "Capex", capex_hist, lambda x, p, i: f"{c('capex_g', x)}*{N['execution']}")
    line("transfer", "Assets commissioned (CWIP to block)",
         (h.fixed_assets.diff() + h.depreciation).to_dict(),
         lambda x, p, i: f"({c('cwip', p)}+{c('capex', x)})*{N['capz']}")

    line("dnwc", "Increase in net working capital",
         fc=lambda x, p, i: f"({c('oa', x)}-{c('ol', x)})-({c('oa', p)}-{c('ol', p)})")
    line("cfo", "Cash from operations", h.cfo.to_dict(), lambda x, p, i: f"{c('pat', x)}+{c('dep', x)}-{c('dnwc', x)}")
    line("cfi", "Cash from investing", h.cfi.to_dict(), lambda x, p, i: f"-{c('capex', x)}-({c('inv', x)}-{c('inv', p)})")
    line("cff", "Cash from financing", h.cff.to_dict(), lambda x, p, i: f"({c('debt', x)}-{c('debt', p)})-{c('div', x)}")

    line("nd_ebitda", "Net debt / EBITDA", fmt="x",
         hist_formula=lambda y: f"={c('debt', L[y])}/{c('ebitda', L[y])}",
         fc=lambda x, p, i: f"({c('debt', x)}-{c('cash', x)})/{c('ebitda', x)}")
    line("roe", "Return on average equity", fmt="pct",
         fc=lambda x, p, i: f"{c('pat', x)}/(({c('eqc', x)}+{c('res', x)}+{c('eqc', p)}+{c('res', p)})/2)")

    M = lambda key, y: f"Model!${L[y]}${R[key] + 1}"  # noqa: E731

    # --------------------------------------------------------------------- DCF
    d = bk.sheet("DCF", {0: 36})
    d.write(0, 0, f"{COVERAGE[ticker]} - valuation", F["title"])
    d.write_row(2, 0, ["Cost of capital", "", "Value"], F["h"])
    wacc_rows = [
        ("rf", "Risk-free (INR, G-sec less default spread)", f"={N['gsec']}-{N['ds']}", "pct"),
        ("beta", "Beta (Blume-adjusted)", f"=0.67*{N['beta_raw']}+0.33", "dec"),
        ("ke", "Cost of equity", None, "pct"),
        ("kd_at", "Post-tax cost of debt", f"={N['kd']}*(1-{N['tax']})", "pct"),
        ("debt0", "Borrowings FY26", f"={M('debt', BASE_FY)}", "num"),
        ("mcap", "Market cap", f"={N['price']}*{N['shares']}", "num"),
        ("wd", "Debt weight", None, "pct"),
        ("wacc", "WACC", None, "pct"),
    ]
    D = {}
    for i, (k, lab, f_, fm) in enumerate(wacc_rows):
        D[k] = f"$C${4 + i}"
        d.write(3 + i, 0, lab, F["lbl"])
    d.write_formula(3, 2, wacc_rows[0][2], F["pct"])
    d.write_formula(4, 2, wacc_rows[1][2], F["dec"])
    d.write_formula(5, 2, f"={D['rf']}+{D['beta']}*{N['erp']}", F["pct"])
    d.write_formula(6, 2, wacc_rows[3][2], F["pct"])
    d.write_formula(7, 2, wacc_rows[4][2], F["num"])
    d.write_formula(8, 2, wacc_rows[5][2], F["num"])
    d.write_formula(9, 2, f"={D['debt0']}/({D['debt0']}+{D['mcap']})", F["pct"])
    d.write_formula(10, 2, f"=(1-{D['wd']})*{D['ke']}+{D['wd']}*{D['kd_at']}", F["pct"])
    wb.define_name("wacc", f"=DCF!{D['wacc']}")
    WACC = f"DCF!{D['wacc']}"

    top = 13
    d.write(top - 1, 0, "Free cash flow to firm", F["h"])
    for y in FC_YEARS:
        d.write(top - 1, COL[y] - 5, fy_label(y, True), F["h"])
    fc_cols = {y: xl_col_to_name(COL[y] - 5) for y in FC_YEARS}      # C..I
    rows = ["NOPAT", "Depreciation", "Capex", "Increase in NWC", "FCFF", "FCFF (stub-adjusted)",
            "Discount period (yrs)", "Discount factor", "PV of FCFF"]
    for i, lab in enumerate(rows):
        d.write(top + i, 0, lab, F["lbl"])
    for i, y in enumerate(FC_YEARS):
        cc = fc_cols[y]
        cell = lambda k: f"{cc}{top + 1 + rows.index(k)}"  # noqa: E731
        d.write_formula(top, COL[y] - 5, f"=({M('ebitda', y)}-{M('dep', y)})*(1-{N['tax']})", F["num"])
        d.write_formula(top + 1, COL[y] - 5, f"={M('dep', y)}", F["num"])
        d.write_formula(top + 2, COL[y] - 5, f"=-{M('capex', y)}", F["num"])
        d.write_formula(top + 3, COL[y] - 5, f"=-{M('dnwc', y)}", F["num"])
        d.write_formula(top + 4, COL[y] - 5, f"=SUM({cc}{top + 1}:{cc}{top + 4})", F["num_b"])
        d.write_formula(top + 5, COL[y] - 5, f"={cell('FCFF')}*{N['stub'] if i == 0 else 1}", F["num"])
        d.write_formula(top + 6, COL[y] - 5, f"={N['stub']}+{i}", F["dec"])
        d.write_formula(top + 7, COL[y] - 5, f"=1/(1+{WACC})^{cell('Discount period (yrs)')}", F["dec"])
        d.write_formula(top + 8, COL[y] - 5, f"={cell('FCFF (stub-adjusted)')}*{cell('Discount factor')}", F["num"])
    first, last = fc_cols[FC_YEARS[0]], fc_cols[FC_YEARS[-1]]
    nopat_last = f"{last}{top + 1}"
    period_last = f"{last}{top + 7}"

    b = top + 11
    bridge = [
        ("pv_fcff", "PV of explicit FCFF", f"=SUM({first}{top + 9}:{last}{top + 9})", "num"),
        ("tv", "Terminal value (value-driver)", f"={nopat_last}*(1+{N['g']})*(1-{N['g']}/{N['ronic']})/({WACC}-{N['g']})", "num"),
        ("pv_tv", "PV of terminal value", None, "num"),
        ("ev", "Enterprise value", None, "num_b"),
        ("less_debt", "Less: borrowings FY26", f"=-{M('debt', BASE_FY)}", "num"),
        ("plus_cash", "Add: cash", f"={N['cash']}", "num"),
        ("plus_inv", "Add: investments (book)", f"={M('inv', BASE_FY)}", "num"),
        ("less_mi", "Less: minority interest", f"=-{N['mi']}", "num"),
        ("eq", "Equity value", None, "num_b"),
        ("dcf_ps", "DCF value per share (Rs)", None, "big"),
        ("tv_share", "Terminal value share of EV", None, "pct"),
        ("rel_ev", "Peer EV/EBITDA x FY26A EBITDA", f"={N['mult']}*{M('ebitda', BASE_FY)}", "num"),
        ("rel_ps", "Relative value per share (Rs)", None, "big"),
        ("tp", "Target price (Rs)", None, "big"),
        ("upside", "Upside / (downside)", None, "pct"),
        ("rating", "Rating", None, "lbl"),
    ]
    B = {k: f"$C${b + 1 + i}" for i, (k, *_rest) in enumerate(bridge)}
    for i, (k, lab, f_, fm) in enumerate(bridge):
        d.write(b + i, 0, lab, F["lbl"])
        if f_:
            d.write_formula(b + i, 2, f_, F[fm])
    d.write_formula(b + 2, 2, f"={B['tv']}/(1+{WACC})^{period_last}", F["num"])
    d.write_formula(b + 3, 2, f"={B['pv_fcff']}+{B['pv_tv']}", F["num_b"])
    d.write_formula(b + 8, 2, f"=SUM({B['ev']},{B['less_debt']},{B['plus_cash']},{B['plus_inv']},{B['less_mi']})", F["num_b"])
    d.write_formula(b + 9, 2, f"={B['eq']}/{N['shares']}", F["big"])
    d.write_formula(b + 10, 2, f"={B['pv_tv']}/{B['ev']}", F["pct"])
    d.write_formula(b + 12, 2, f"=({B['rel_ev']}-{M('debt', BASE_FY)}+{N['cash']}-{N['mi']})/{N['shares']}", F["big"])
    d.write_formula(b + 13, 2, f"={N['w_dcf']}*{B['dcf_ps']}+(1-{N['w_dcf']})*{B['rel_ps']}", F["big"])
    d.write_formula(b + 14, 2, f"={B['tp']}/{N['price']}-1", F["pct"])
    d.write_formula(b + 15, 2, f'=IF({B["upside"]}>0.15,"BUY",IF({B["upside"]}<-0.1,"SELL","HOLD"))', F["h"])
    for k in ("dcf_ps", "rel_ps", "tp", "upside", "rating"):
        wb.define_name(f"out_{k}", f"=DCF!{B[k]}")

    # sensitivity: DCF value per share across WACC x g, all live formulas
    s0 = b + 18
    d.write(s0, 0, "DCF value per share: WACC (rows) x terminal growth (cols)", F["h"])
    gs = [0.04, 0.045, 0.05, 0.055, 0.06]
    dw = [-0.01, -0.005, 0, 0.005, 0.01]
    for j, g in enumerate(gs):
        d.write(s0 + 1, 2 + j, g, F["in_pct"])
    fcff_rng = f"${first}${top + 6}:${last}${top + 6}"
    per_rng = f"${first}${top + 7}:${last}${top + 7}"
    for i, dv in enumerate(dw):
        rr = s0 + 2 + i
        d.write_formula(rr, 1, f"={WACC}+{dv}", F["pct"])
        for j in range(len(gs)):
            gcell = xl_rowcol_to_cell(s0 + 1, 2 + j, row_abs=True)
            wcell = xl_rowcol_to_cell(rr, 1, col_abs=True)
            f_ = (f"=(SUMPRODUCT({fcff_rng}/(1+{wcell})^{per_rng})"
                  f"+${last}${top + 1}*(1+{gcell})*(1-{gcell}/{N['ronic']})/({wcell}-{gcell})/(1+{wcell})^${last}${top + 7}"
                  f"-{M('debt', BASE_FY)}+{N['cash']}+{M('inv', BASE_FY)}-{N['mi']})/{N['shares']}")
            d.write_formula(rr, 2 + j, f_, F["num"])

    # ------------------------------------------------------------------- Cover
    cv = wb.add_worksheet("Cover")
    cv.hide_gridlines(2)
    cv.set_column(0, 0, 30)
    cv.set_column(1, 1, 16)
    cv.write(0, 0, COVERAGE[ticker], F["title"])
    O = {k: f"DCF!{B[k]}" for k in B}
    items = [("Rating", f"={O['rating']}", "h"), ("Target price (Rs)", f"={O['tp']}", "big"),
             ("Current price (Rs)", f"={N['price']}", "num"), ("Upside", f"={O['upside']}", "pct"),
             ("DCF value (Rs)", f"={O['dcf_ps']}", "num"), ("Peer-multiple value (Rs)", f"={O['rel_ps']}", "num"),
             ("WACC", f"={WACC}", "pct")]
    for i, (lab, f_, fm) in enumerate(items):
        cv.write(2 + i, 0, lab, F["lbl"])
        cv.write_formula(2 + i, 1, f_, F[fm])
    cv.write(10, 0, "Blue = input, black = formula. Change Inputs or the capex/margin rows on Model.", F["note"])
    cv.write(11, 0, f"Prices as of {mkt.price_date}. Student research exercise, not investment advice.", F["note"])
    cv.activate()
    cv.set_first_sheet()

    # ------------------------------------------------------------------- Comps
    cp = bk.sheet("Comps", {0: 22, 1: 22})
    comps = pd.read_csv(PROCESSED / "comps.csv", index_col=0)
    cols = ["segment", "mcap_cr", "ev_cr", "ev_ebitda", "pe", "pb", "roe", "ebitda_margin", "nd_ebitda"]
    heads = ["Segment", "Mcap", "EV", "EV/EBITDA", "P/E", "P/B", "ROE", "EBITDA margin", "ND/EBITDA"]
    cp.write(0, 0, "Listed power comps, FY26A", F["title"])
    cp.write_row(2, 0, ["Company"] + heads, F["h"])
    fmts = [None, "num", "num", "x", "x", "x", "pct", "pct", "x"]
    for i, (t, r_) in enumerate(comps.sort_values("mcap_cr", ascending=False).iterrows()):
        cp.write(3 + i, 0, r_["name"], F["lbl"])
        for j, (col, fm) in enumerate(zip(cols, fmts)):
            v = r_[col]
            if fm is None:
                cp.write(3 + i, 1 + j, v, F["lbl"])
            elif pd.notna(v):
                cp.write(3 + i, 1 + j, float(v), F[fm])

    # ---------------------------------------------------------------- Guidance
    gd = bk.sheet("Guidance", {0: 10, 1: 6, 2: 30, 3: 110})
    g = pd.read_csv(PROCESSED / "guidance_sentences.csv")
    g = g[g.ticker == ticker].sort_values("date", ascending=False)
    gd.write(0, 0, "Management guidance extracted from earnings calls (NSE filings)", F["title"])
    gd.write_row(2, 0, ["Call", "Page", "Figures", "Sentence"], F["h"])
    for i, r_ in enumerate(g.head(150).itertuples()):
        gd.write_row(3 + i, 0, [r_.call, r_.page, r_.figures, r_.sentence], F["wrap"])

    wb.worksheets_objs.sort(key=lambda s: ["Cover", "Inputs", "Model", "DCF", "Comps", "Guidance"].index(s.name))
    wb.close()
    return str(path)


if __name__ == "__main__":
    for t in COVERAGE:
        print(build(t))
