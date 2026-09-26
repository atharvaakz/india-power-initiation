"""Write each covered company's model as an Excel workbook with live formulas.

Sheets: Cover | Inputs | Model (capacity build, IS/BS/CF, FY22A-FY36E) | DCF (WACC, FCFF, TV,
bridge, 12-month values, sensitivity) | SOTP (NTPC) | Comps | Guidance.
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
FC_YEARS = list(range(BASE_FY + 1, BASE_FY + 1 + N_FORECAST))  # FY27E..FY36E
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
    from .forecast import KWH_FACTOR, base_state
    st = base_state(ticker)
    reg = a["regulated"]
    inp = bk.sheet("Inputs", {2: 14, 3: 90})
    inp.write(0, 0, f"{COVERAGE[ticker]} - inputs (Rs crore)", F["title"])
    R_ = a["rationale"]
    scalars = [
        ("gsec", "India 10Y G-sec yield", MARKET["gsec_10y"], "in_pct", "Trading Economics, 25-Sep-2026"),
        ("ds", "Sovereign default spread", MARKET["default_spread"], "in_pct", "Damodaran, Jan-2026 (Baa3)"),
        ("erp", "Equity risk premium (India, total)", MARKET["erp"], "in_pct", "Damodaran, Jan-2026"),
        ("tax", "Tax rate", MARKET["tax"], "in_pct", "New corporate regime, 25.17% rounded"),
        ("stub", "FY27 fraction remaining", MARKET["stub"], "in_dec", "Valuation date 25-Sep-2026"),
        ("w_dcf", "Weight on 12m DCF in target (non-regulated)", MARKET["dcf_weight"], "in_pct", "Balance on FY27E EV/EBITDA"),
        ("min_cash", "Incremental cash floor", MARKET["min_cash"], "in_num", "Shortfalls drawn on a revolver"),
        ("beta_raw", "Raw beta (2y weekly vs Nifty 50)", mkt.beta_2y_weekly, "in_dec", "Computed from NSE prices"),
        ("kd", "Pre-tax cost of debt", a["kd"], "in_pct", a["rf_spread_note"]),
        ("g", "Terminal growth", a["g"], "in_pct", "Nominal INR"),
        ("ronic", "Return on new invested capital (terminal)", a["ronic"], "in_pct", ""),
        ("price", "Share price (Rs)", mkt.price, "in_num", f"NSE close {mkt.price_date}"),
        ("shares", "Shares outstanding (crore)", mkt.shares_cr, "in_dec", "NSE / yfinance"),
        ("cash", "Cash & short-term investments FY26", mkt.cash_cr, "in_num", "FY26 balance sheet"),
        ("mi", "Minority interest FY26", mkt.minority_cr, "in_num", "FY26 balance sheet"),
        ("mult", "Peer median EV/EBITDA FY26A", peer_multiple(ticker), "x", "Peers: " + ", ".join(p for p in PEER_SETS[ticker] if p != ticker)),
        ("execution", "Capex execution vs guidance", a["execution"], "in_pct", R_["capex"]),
        ("re_share", "RE share of assets commissioned", a["re_share"], "in_pct", R_["renewables"]),
        ("re_cost", "RE cost (Rs cr per MW)", a["re_cost"], "in_dec", ""),
        ("re_cuf", "RE capacity utilisation (CUF)", a["re_cuf"], "in_pct", ""),
        ("re_tariff", "RE tariff (Rs/kWh)", a["re_tariff"], "in_dec", ""),
        ("re_margin", "RE EBITDA margin", a["re_margin"], "in_pct", ""),
        ("re_mw_prev", "RE MW at FY25 (for FY26 calibration)", a["re_mw_prev"], "in_num", ""),
        ("re_mw0", "RE MW at FY26", st["mw"], "in_num", "NTPC: reported; others: FY26 RE commissioning / cost per MW"),
        ("jv0", "Share of JV profit FY26", a["jv_profit0"], "in_num", "Q4FY26 call" if a["jv_profit0"] else "not modelled"),
        ("jv_g", "JV profit growth", a["jv_growth"], "in_pct", ""),
        ("oi", "Other income % of sales", a["other_income_pct"], "in_pct", ""),
        ("dep", "Depreciation % opening net block", a["dep_rate"], "in_pct", ""),
        ("capz", "Capitalisation % of (CWIP + capex)", a["capitalisation"], "in_pct", ""),
        ("debt_share", "New term debt % of capex", a["debt_share"], "in_pct", ""),
        ("int", "Interest % average debt (and revolver)", a["int_rate"], "in_pct", ""),
        ("payout", "Dividend payout", a["payout"], "in_pct", "FY26 actual"),
        ("oa", "Other (non-cash) assets % of sales", a["oa_pct"], "in_pct", ""),
        ("ol", "Other liabilities (ex minorities) % of sales", a["ol_pct"], "in_pct", ""),
        ("inv_g", "Investments growth (cash)", a["inv_growth"], "in_pct", ""),
    ]
    if reg:
        scalars += [
            ("regeq_prev", "Regulated equity FY25", a["regeq_prev"], "in_num", R_["regulated"]),
            ("regeq0", "Regulated equity FY26", a["regeq0"], "in_num", ""),
            ("regshare", "Normative equity share of regulated capital", a["reg_equity_share"], "in_pct", "CERC"),
            ("roe", "Earned RoE on regulated equity", a["roe"], "in_pct", "15.5% normative + net operational gains"),
            ("pb_g", "Regulated equity growth after FY36", a["pb_growth"], "in_pct", ""),
            ("ngel_mcap", "NTPC Green market cap", float(mkt.listed_sub_mcap_cr), "in_num", f"NSE {mkt.price_date}"),
            ("ngel_stake", "NTPC stake in NTPC Green", a["ngel_stake"], "in_pct", "Jun-2026 shareholding"),
            ("holdco", "Holding-company discount", MARKET["holdco_discount"], "in_pct", ""),
        ]
    else:
        scalars += [
            ("drift", "EBITDA growth of existing assets", a["base_drift"], "in_pct", R_["core"]),
            ("yield", "EBITDA yield on non-RE assets commissioned", a["asset_yield"], "in_pct", ""),
        ]
    N = {}
    inp.write_row(2, 0, ["Input", "", "Value", "Source / rationale"], F["h"])
    for i, (key, label, val, fmt, src) in enumerate(scalars):
        r = 3 + i
        inp.write(r, 0, label, F["lbl"])
        inp.write(r, 2, val, F[fmt] if fmt != "x" else F["x"])
        inp.write(r, 3, src, F["note"])
        wb.define_name(f"in_{key}", f"=Inputs!$C${r + 1}")
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
    layout = ["#Capex and commissioning", "capex_g", "capex", "transfer", "re_transfer", "nonre_transfer",
              "#EBITDA build", "re_mw", "re_rev", "re_ebitda", "regeq", "core", "ebitda", "margin",
              "#Income statement", "sales", "oi", "dep", "int", "pbt", "tax", "jv", "pat", "mi_pat", "pat_attr",
              "eps", "div",
              "#Balance sheet", "fa", "cwip", "inv", "oa", "cash", "ta", "eqc", "res", "mi", "debt", "rev", "ol",
              "tl", "check",
              "#Cash flow", "dnwc", "cfo", "cfi", "cff_pre", "pre_cash", "draw", "cff",
              "#Ratios", "nd_ebitda", "roe"]
    R = {k: 3 + i for i, k in enumerate(layout) if not k.startswith("#")}
    SEC = {k[1:]: 3 + i for i, k in enumerate(layout) if k.startswith("#")}

    def section(title):
        r = SEC[title]
        ws.write(r, 0, title, F["sec"])
        for c in range(1, COL[FC_YEARS[-1]] + 1):
            ws.write_blank(r, c, None, F["sec"])

    def line(key, label, hist_vals=None, fc=None, fmt="num", hist_formula=None, base=None):
        """base: value or formula string for the FY26A column (overrides history there)."""
        r = R[key]
        ws.write(r, 0, label, F["lbl"])
        for y in HIST_YEARS:
            if hist_formula:
                ws.write_formula(r, COL[y], hist_formula(y), F[fmt])
            elif hist_vals is not None:
                v = hist_vals.get(y)
                if v is not None and pd.notna(v):
                    ws.write(r, COL[y], float(v), F[fmt])
        if base is not None:
            if isinstance(base, str):
                ws.write_formula(r, COL[BASE_FY], base, F[fmt])
            else:
                ws.write(r, COL[BASE_FY], float(base), F[fmt])
        if fc:
            for i, y in enumerate(FC_YEARS):
                ws.write_formula(r, COL[y], "=" + fc(L[y], L[y - 1], i), F[fmt])

    def c(key, col):
        return f"{col}{R[key] + 1}"

    B0 = L[BASE_FY]
    h = hist
    for title in SEC:
        section(title)
    ws.write(R["capex_g"], 0, "Capex guided (mgmt)", F["lbl"])
    for i, y in enumerate(FC_YEARS):
        ws.write(R["capex_g"], COL[y], a["capex_guided"][i], F["in_num"])

    capex_hist = (h.fixed_assets.diff() + h.depreciation + h.cwip.diff()).to_dict()
    line("capex", "Capex", capex_hist, lambda x, p, i: f"{c('capex_g', x)}*{N['execution']}")
    line("transfer", "Assets commissioned (CWIP to block)", (h.fixed_assets.diff() + h.depreciation).to_dict(),
         lambda x, p, i: f"({c('cwip', p)}+{c('capex', x)})*{N['capz']}")
    line("re_transfer", "  of which renewables", base=f"={c('transfer', B0)}*{N['re_share']}",
         fc=lambda x, p, i: f"{c('transfer', x)}*{N['re_share']}")
    line("nonre_transfer", "  of which core / regulated", base=f"={c('transfer', B0)}-{c('re_transfer', B0)}",
         fc=lambda x, p, i: f"{c('transfer', x)}-{c('re_transfer', x)}")

    rev_formula = lambda mw_p, mw_x: f"({mw_p}+{mw_x})/2*{N['re_cuf']}*{KWH_FACTOR}*{N['re_tariff']}"  # noqa: E731
    line("re_mw", "Renewable capacity (MW)", base=f"={N['re_mw0']}",
         fc=lambda x, p, i: f"{c('re_mw', p)}+{c('re_transfer', x)}/{N['re_cost']}")
    line("re_rev", "Renewable revenue", base="=" + rev_formula(N["re_mw_prev"], N["re_mw0"]),
         fc=lambda x, p, i: rev_formula(c("re_mw", p), c("re_mw", x)))
    line("re_ebitda", "Renewable EBITDA", base=f"={c('re_rev', B0)}*{N['re_margin']}",
         fc=lambda x, p, i: f"{c('re_rev', x)}*{N['re_margin']}")
    if reg:
        avg0 = f"(({N['regeq_prev']}+{N['regeq0']})/2)"
        line("regeq", "Regulated equity", base=f"={N['regeq0']}",
             fc=lambda x, p, i: f"{c('regeq', p)}+{N['regshare']}*{c('nonre_transfer', x)}")
        line("core", "Regulated (core) EBITDA", base=f"={c('ebitda', B0)}-{c('re_ebitda', B0)}",
             fc=lambda x, p, i: f"${B0}${R['core'] + 1}*({c('regeq', p)}+{c('regeq', x)})/2/{avg0}")
    else:
        line("regeq", "Regulated equity (n/a)")
        line("core", "Core EBITDA", base=f"={c('ebitda', B0)}-{c('re_ebitda', B0)}",
             fc=lambda x, p, i: f"{c('core', p)}*(1+{N['drift']})+{N['yield']}*0.5*({c('nonre_transfer', p)}+{c('nonre_transfer', x)})")
    line("ebitda", "EBITDA", h.operating_profit.to_dict(), lambda x, p, i: f"{c('core', x)}+{c('re_ebitda', x)}")
    core_margin = f"(${B0}${R['core'] + 1}/(${B0}${R['sales'] + 1}-${B0}${R['re_rev'] + 1}))"
    line("margin", "EBITDA margin", fmt="pct", hist_formula=lambda y: f"={c('ebitda', L[y])}/{c('sales', L[y])}",
         fc=lambda x, p, i: f"{c('ebitda', x)}/{c('sales', x)}")

    line("sales", "Revenue", h.sales.to_dict(), lambda x, p, i: f"{c('core', x)}/{core_margin}+{c('re_rev', x)}")
    line("oi", "Other income", h.other_income.to_dict(), lambda x, p, i: f"{c('sales', x)}*{N['oi']}")
    line("dep", "Depreciation", h.depreciation.to_dict(), lambda x, p, i: f"{c('fa', p)}*{N['dep']}")
    line("int", "Interest (term debt + opening revolver)", h.interest.to_dict(),
         lambda x, p, i: f"({c('debt', p)}+{c('debt', x)})/2*{N['int']}+{c('rev', p)}*{N['int']}")
    line("pbt", "Profit before tax", h.pbt.to_dict(),
         lambda x, p, i: f"{c('ebitda', x)}+{c('oi', x)}-{c('dep', x)}-{c('int', x)}")
    line("tax", "Tax", (h.pbt - h.net_profit).to_dict(), lambda x, p, i: f"MAX({c('pbt', x)},0)*{N['tax']}")
    line("jv", "Share of JV profit", base=f"={N['jv0']}", fc=lambda x, p, i: f"{c('jv', p)}*(1+{N['jv_g']})")
    line("pat", "Net profit", h.net_profit.to_dict(), lambda x, p, i: f"{c('pbt', x)}-{c('tax', x)}+{c('jv', x)}")
    mi_share = f"({N['mi']}/({c('eqc', '$' + B0)}+{c('res', '$' + B0)}+{N['mi']}))"
    line("mi_pat", "Minority share of profit", fc=lambda x, p, i: f"({c('pbt', x)}-{c('tax', x)})*{mi_share}")
    line("pat_attr", "Net profit to shareholders", fc=lambda x, p, i: f"{c('pat', x)}-{c('mi_pat', x)}")
    line("eps", "EPS (Rs)", fmt="dec", hist_formula=lambda y: f"={c('pat', L[y])}/{N['shares']}",
         fc=lambda x, p, i: f"{c('pat_attr', x)}/{N['shares']}")
    line("div", "Dividends", fc=lambda x, p, i: f"MAX({c('pat_attr', x)},0)*{N['payout']}")

    oa0 = h.loc[BASE_FY, ["equity_capital", "reserves", "borrowings", "other_liabilities"]].sum() - \
        h.loc[BASE_FY, ["fixed_assets", "cwip", "investments"]].sum()
    line("fa", "Net block", h.fixed_assets.to_dict(), lambda x, p, i: f"{c('fa', p)}+{c('transfer', x)}-{c('dep', x)}")
    line("cwip", "Capital work in progress", h.cwip.to_dict(),
         lambda x, p, i: f"{c('cwip', p)}+{c('capex', x)}-{c('transfer', x)}")
    line("inv", "Investments", h.investments.to_dict(),
         lambda x, p, i: f"{c('inv', p)}*(1+{N['inv_g']})+{c('jv', x)}")
    oa_hist = h.other_assets.to_dict()
    oa_hist[BASE_FY] = oa0
    line("oa", "Other assets (non-cash)", oa_hist, lambda x, p, i: f"{c('sales', x)}*{N['oa']}")
    line("cash", "Incremental cash (floor, see revolver)", base=0.0,
         fc=lambda x, p, i: f"{c('pre_cash', x)}+{c('draw', x)}")
    line("ta", "Total assets", fmt="num_b",
         hist_formula=lambda y: f"={c('fa', L[y])}+{c('cwip', L[y])}+{c('inv', L[y])}+{c('oa', L[y])}"
                                + (f"+{c('cash', L[y])}" if y == BASE_FY else ""),
         fc=lambda x, p, i: f"{c('fa', x)}+{c('cwip', x)}+{c('inv', x)}+{c('oa', x)}+{c('cash', x)}")
    line("eqc", "Equity capital", h.equity_capital.to_dict(), lambda x, p, i: c("eqc", p))
    line("res", "Reserves", h.reserves.to_dict(),
         lambda x, p, i: f"{c('res', p)}+{c('pat_attr', x)}-{c('div', x)}")
    line("mi", "Minority interest", base=f"={N['mi']}", fc=lambda x, p, i: f"{c('mi', p)}+{c('mi_pat', x)}")
    line("debt", "Borrowings (term)", h.borrowings.to_dict(),
         lambda x, p, i: f"{c('debt', p)}+{c('capex', x)}*{N['debt_share']}")
    line("rev", "Revolver", base=0.0, fc=lambda x, p, i: f"{c('rev', p)}+{c('draw', x)}")
    ol_hist = h.other_liabilities.to_dict()
    line("ol", "Other liabilities (ex minorities from FY26)", ol_hist,
         lambda x, p, i: f"{c('sales', x)}*{N['ol']}",
         base=f"={float(h.loc[BASE_FY, 'other_liabilities'])}-{N['mi']}")
    tl_parts = ["eqc", "res", "mi", "debt", "rev", "ol"]
    line("tl", "Total liabilities & equity", fmt="num_b",
         hist_formula=lambda y: "=" + "+".join(c(k, L[y]) for k in tl_parts),
         fc=lambda x, p, i: "+".join(c(k, x) for k in tl_parts))
    line("check", "Balance check (assets - liabilities)", fmt="chk",
         hist_formula=lambda y: f"=IF(ABS({c('ta', L[y])}-{c('tl', L[y])})<2,0,{c('ta', L[y])}-{c('tl', L[y])})",
         fc=lambda x, p, i: f"ROUND({c('ta', x)}-{c('tl', x)},4)")

    line("dnwc", "Increase in net working capital",
         fc=lambda x, p, i: f"({c('oa', x)}-{c('ol', x)})-({c('oa', p)}-{c('ol', p)})")
    line("cfo", "Cash from operations", h.cfo.to_dict(),
         lambda x, p, i: f"{c('pat', x)}-{c('jv', x)}+{c('dep', x)}-{c('dnwc', x)}")
    line("cfi", "Cash from investing", h.cfi.to_dict(),
         lambda x, p, i: f"-{c('capex', x)}-{c('inv', p)}*{N['inv_g']}")
    line("cff_pre", "Term debt raised less dividends",
         fc=lambda x, p, i: f"{c('capex', x)}*{N['debt_share']}-{c('div', x)}")
    line("pre_cash", "Cash before revolver", base=0.0,
         fc=lambda x, p, i: f"{c('cash', p)}+{c('cfo', x)}+{c('cfi', x)}+{c('cff_pre', x)}")
    line("draw", "Revolver draw / (repayment)",
         fc=lambda x, p, i: f"MAX({N['min_cash']}-{c('pre_cash', x)},-{c('rev', p)})")
    line("cff", "Cash from financing", h.cff.to_dict(), lambda x, p, i: f"{c('cff_pre', x)}+{c('draw', x)}")

    line("nd_ebitda", "Net debt / EBITDA", fmt="x",
         hist_formula=lambda y: f"={c('debt', L[y])}/{c('ebitda', L[y])}",
         fc=lambda x, p, i: f"({c('debt', x)}+{c('rev', x)}-{c('cash', x)})/{c('ebitda', x)}")
    line("roe", "Return on average equity", fmt="pct",
         fc=lambda x, p, i: f"{c('pat_attr', x)}/(({c('eqc', x)}+{c('res', x)}+{c('eqc', p)}+{c('res', p)})/2)")

    M = lambda key, y: f"Model!${L[y]}${R[key] + 1}"  # noqa: E731
    Y1 = FC_YEARS[0]

    # --------------------------------------------------------------------- DCF
    d = bk.sheet("DCF", {0: 40})
    d.write(0, 0, f"{COVERAGE[ticker]} - valuation", F["title"])
    d.write_row(2, 0, ["Cost of capital", "", "Value"], F["h"])
    labels = ["Risk-free (INR, G-sec less default spread)", "Beta (Blume-adjusted)", "Cost of equity",
              "Post-tax cost of debt", "Borrowings FY26", "Market cap", "Debt weight", "WACC"]
    keys = ["rf", "beta", "ke", "kd_at", "debt0", "mcap", "wd", "wacc"]
    D = {k: f"$C${4 + i}" for i, k in enumerate(keys)}
    for i, lab in enumerate(labels):
        d.write(3 + i, 0, lab, F["lbl"])
    d.write_formula(3, 2, f"={N['gsec']}-{N['ds']}", F["pct"])
    d.write_formula(4, 2, f"=0.67*{N['beta_raw']}+0.33", F["dec"])
    d.write_formula(5, 2, f"={D['rf']}+{D['beta']}*{N['erp']}", F["pct"])
    d.write_formula(6, 2, f"={N['kd']}*(1-{N['tax']})", F["pct"])
    d.write_formula(7, 2, f"={M('debt', BASE_FY)}", F["num"])
    d.write_formula(8, 2, f"={N['price']}*{N['shares']}", F["num"])
    d.write_formula(9, 2, f"={D['debt0']}/({D['debt0']}+{D['mcap']})", F["pct"])
    d.write_formula(10, 2, f"=(1-{D['wd']})*{D['ke']}+{D['wd']}*{D['kd_at']}", F["pct"])
    wb.define_name("wacc", f"=DCF!{D['wacc']}")
    WACC, KE = f"DCF!{D['wacc']}", f"DCF!{D['ke']}"

    top = 13
    d.write(top - 1, 0, "Free cash flow to firm", F["h"])
    fc_cols = {y: xl_col_to_name(2 + i) for i, y in enumerate(FC_YEARS)}
    for i, y in enumerate(FC_YEARS):
        d.write(top - 1, 2 + i, fy_label(y, True), F["h"])
    rows = ["NOPAT", "Depreciation", "Capex", "Increase in NWC", "FCFF", "FCFF (stub-adjusted)",
            "Discount period (yrs)", "Discount factor", "PV of FCFF"]
    for i, lab in enumerate(rows):
        d.write(top + i, 0, lab, F["lbl"])
    for i, y in enumerate(FC_YEARS):
        cc, col = fc_cols[y], 2 + i
        cell = lambda k: f"{cc}{top + 1 + rows.index(k)}"  # noqa: E731
        d.write_formula(top, col, f"=({M('ebitda', y)}-{M('dep', y)})*(1-{N['tax']})", F["num"])
        d.write_formula(top + 1, col, f"={M('dep', y)}", F["num"])
        d.write_formula(top + 2, col, f"=-{M('capex', y)}", F["num"])
        d.write_formula(top + 3, col, f"=-{M('dnwc', y)}", F["num"])
        d.write_formula(top + 4, col, f"=SUM({cc}{top + 1}:{cc}{top + 4})", F["num_b"])
        d.write_formula(top + 5, col, f"={cell('FCFF')}*{N['stub'] if i == 0 else 1}", F["num"])
        d.write_formula(top + 6, col, f"={N['stub']}+{i}", F["dec"])
        d.write_formula(top + 7, col, f"=1/(1+{WACC})^{cell('Discount period (yrs)')}", F["dec"])
        d.write_formula(top + 8, col, f"={cell('FCFF (stub-adjusted)')}*{cell('Discount factor')}", F["num"])
    first, last = fc_cols[FC_YEARS[0]], fc_cols[FC_YEARS[-1]]
    nopat_last, period_last = f"{last}{top + 1}", f"{last}{top + 7}"

    b = top + 11
    bridge = [
        ("pv_fcff", "PV of explicit FCFF", f"=SUM({first}{top + 9}:{last}{top + 9})", "num"),
        ("tv", "Terminal value (value-driver)", f"={nopat_last}*(1+{N['g']})*(1-{N['g']}/{N['ronic']})/({WACC}-{N['g']})", "num"),
        ("pv_tv", "PV of terminal value", "PV_TV", "num"),
        ("ev", "Enterprise value", "EV", "num_b"),
        ("less_debt", "Less: borrowings FY26", f"=-{M('debt', BASE_FY)}", "num"),
        ("plus_cash", "Add: cash", f"={N['cash']}", "num"),
        ("plus_inv", "Add: investments (book)", f"={M('inv', BASE_FY)}", "num"),
        ("less_mi", "Less: minority interest", f"=-{N['mi']}", "num"),
        ("eq", "Equity value today", "EQ", "num_b"),
        ("dcf_ps", "DCF value per share today (Rs)", "DCFPS", "big"),
        ("tv_share", "Terminal value share of EV", "TVS", "pct"),
        ("dcf_12m", "DCF value in 12 months (grown at Ke, less FY27 DPS)", "D12", "num"),
        ("rel_ev", "Peer EV/EBITDA x FY27E EBITDA", f"={N['mult']}*{M('ebitda', Y1)}", "num"),
        ("rel_ps", "EV/EBITDA value in 12 months (Rs)", "REL", "num"),
        ("sotp_ps", "SOTP value per share (Rs, regulated only)", "SOTP", "num"),
        ("tp", "12-month target price (Rs)", "TP", "big"),
        ("upside", "Upside / (downside)", "UP", "pct"),
        ("rating", "Rating", "RT", "lbl"),
    ]
    B = {k: f"$C${b + 1 + i}" for i, (k, *_r) in enumerate(bridge)}
    fixed = {
        "PV_TV": f"={B['tv']}/(1+{WACC})^{period_last}",
        "EV": f"={B['pv_fcff']}+{B['pv_tv']}",
        "EQ": f"=SUM({B['ev']},{B['less_debt']},{B['plus_cash']},{B['plus_inv']},{B['less_mi']})",
        "DCFPS": f"={B['eq']}/{N['shares']}",
        "TVS": f"={B['pv_tv']}/{B['ev']}",
        "D12": f"={B['dcf_ps']}*(1+{KE})-{M('div', Y1)}/{N['shares']}",
        "REL": f"=({B['rel_ev']}-{M('debt', Y1)}-{M('rev', Y1)}+{N['cash']}+{M('cash', Y1)}-{M('mi', Y1)})/{N['shares']}",
        "SOTP": "=SOTP!$C$30" if reg else '=NA()',
        "TP": (f"={B['sotp_ps']}" if reg else f"={N['w_dcf']}*{B['dcf_12m']}+(1-{N['w_dcf']})*{B['rel_ps']}"),
        "UP": f"={B['tp']}/{N['price']}-1",
        "RT": f'=IF({B["upside"]}>0.15,"BUY",IF({B["upside"]}<-0.1,"SELL","HOLD"))',
    }
    for i, (k, lab, f_, fm) in enumerate(bridge):
        d.write(b + i, 0, lab, F["lbl"])
        if k == "sotp_ps" and not reg:
            d.write(b + i, 2, "n/a", F["lbl"])
            continue
        d.write_formula(b + i, 2, fixed.get(f_, f_), F["h"] if fm == "lbl" else F[fm])
    for k in ("dcf_ps", "dcf_12m", "rel_ps", "tp", "upside", "rating") + (("sotp_ps",) if reg else ()):
        wb.define_name(f"out_{k}", f"=DCF!{B[k]}")

    s0 = b + len(bridge) + 2
    d.write(s0, 0, "DCF value per share today: WACC (rows) x terminal growth (cols)", F["h"])
    gs = [0.04, 0.045, 0.05, 0.055, 0.06]
    for j, g in enumerate(gs):
        d.write(s0 + 1, 2 + j, g, F["in_pct"])
    fcff_rng = f"${first}${top + 6}:${last}${top + 6}"
    per_rng = f"${first}${top + 7}:${last}${top + 7}"
    for i, dv in enumerate([-0.01, -0.005, 0, 0.005, 0.01]):
        rr = s0 + 2 + i
        d.write_formula(rr, 1, f"={WACC}+{dv}", F["pct"])
        for j in range(len(gs)):
            gcell = xl_rowcol_to_cell(s0 + 1, 2 + j, row_abs=True)
            wcell = xl_rowcol_to_cell(rr, 1, col_abs=True)
            f_ = (f"=(SUMPRODUCT({fcff_rng}/(1+{wcell})^{per_rng})"
                  f"+${last}${top + 1}*(1+{gcell})*(1-{gcell}/{N['ronic']})/({wcell}-{gcell})/(1+{wcell})^${last}${top + 7}"
                  f"-{M('debt', BASE_FY)}+{N['cash']}+{M('inv', BASE_FY)}-{N['mi']})/{N['shares']}")
            d.write_formula(rr, 2 + j, f_, F["num"])

    # ------------------------------------------------------------------- SOTP (regulated)
    if reg:
        so = bk.sheet("SOTP", {0: 46})
        so.write(0, 0, f"{COVERAGE[ticker]} - sum of the parts at Mar-27", F["title"])
        so.write(2, 0, "Residual income on regulated equity", F["h"])
        so.write_row(3, 0, ["", "t"], F["h"])
        lab = ["Regulated equity (closing)", "Residual income (RoE - Ke) x opening", "Discount factor", "PV"]
        for k, t in enumerate(lab):
            so.write(4 + k, 0, t, F["lbl"])
        for i, y in enumerate(FC_YEARS):
            col = 2 + i
            cc = xl_col_to_name(col)
            pc = xl_col_to_name(col - 1)
            so.write(3, col, fy_label(y, True), F["h"])
            so.write_formula(4, col, f"={M('regeq', y)}", F["num"])
            if i > 0:
                so.write_formula(5, col, f"=({N['roe']}-{KE})*{pc}5", F["num"])
                so.write_formula(6, col, f"=1/(1+{KE})^{i}", F["dec"])
                so.write_formula(7, col, f"={cc}6*{cc}7", F["num"])
        lc = xl_col_to_name(2 + len(FC_YEARS) - 1)
        n = len(FC_YEARS) - 1
        parts = [
            ("Regulated equity FY27E (book)", "=$C$5"),
            ("PV of residual income FY28-FY36", f"=SUM(D8:{lc}8)"),
            ("PV of terminal residual income", f"=({N['roe']}-{KE})*{lc}5/({KE}-{N['pb_g']})/(1+{KE})^{n}"),
            ("Regulated equity value", "=SUM(C11:C13)"),
            ("Implied P/B on FY27E regulated equity", "=C14/C11"),
            ("Equity in regulated CWIP at book", f"={N['regshare']}*(1-{N['re_share']})*{M('cwip', Y1)}"),
            ("NTPC Green stake at market less holdco discount", f"={N['ngel_stake']}*{N['ngel_mcap']}*(1-{N['holdco']})"),
        ]
        for i, (t, f_) in enumerate(parts):
            so.write(10 + i, 0, t, F["lbl"])
            so.write_formula(10 + i, 2, f_, F["x"] if "P/B" in t else F["num"])
        so.write(28, 0, "Equity value", F["lbl"])
        so.write_formula(28, 2, "=C14+C16+C17", F["num_b"])
        so.write(29, 0, "SOTP value per share (Rs)", F["lbl"])
        so.write_formula(29, 2, f"=C29/{N['shares']}", F["big"])
        so.write(31, 0, "JVs are not added: consolidated regulated equity already includes them.", F["note"])

    # ------------------------------------------------------------------- Cover
    cv = wb.add_worksheet("Cover")
    cv.hide_gridlines(2)
    cv.set_column(0, 0, 34)
    cv.set_column(1, 1, 16)
    cv.write(0, 0, COVERAGE[ticker], F["title"])
    O = {k: f"DCF!{B[k]}" for k in B}
    items = [("Rating", f"={O['rating']}", "h"), ("12-month target price (Rs)", f"={O['tp']}", "big"),
             ("Current price (Rs)", f"={N['price']}", "num"), ("Upside", f"={O['upside']}", "pct"),
             ("DCF value today (Rs)", f"={O['dcf_ps']}", "num"), ("DCF value in 12m (Rs)", f"={O['dcf_12m']}", "num"),
             ("FY27E EV/EBITDA value (Rs)", f"={O['rel_ps']}", "num"), ("WACC", f"={WACC}", "pct")]
    if reg:
        items.insert(4, ("SOTP value (Rs)", f"={O['sotp_ps']}", "num"))
    for i, (lab, f_, fm) in enumerate(items):
        cv.write(2 + i, 0, lab, F["lbl"])
        cv.write_formula(2 + i, 1, f_, F[fm])
    cv.write(12, 0, "Method: " + ("sum of the parts; DCF and EV/EBITDA are cross-checks." if reg
                                  else "50% 12-month DCF + 50% FY27E EV/EBITDA."), F["note"])
    cv.write(13, 0, "Blue = input, black = formula. Change Inputs or the guided-capex row on Model.", F["note"])
    cv.write(14, 0, f"Prices as of {mkt.price_date}. Student research exercise, not investment advice.", F["note"])
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

    order = ["Cover", "Inputs", "Model", "DCF", "SOTP", "Comps", "Guidance"]
    wb.worksheets_objs.sort(key=lambda s: order.index(s.name))
    wb.close()
    return str(path)


if __name__ == "__main__":
    for t in COVERAGE:
        print(build(t))
