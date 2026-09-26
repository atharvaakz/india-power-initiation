"""Assemble the initiation report PDF (ReportLab).

All numbers are pulled from the model at build time, so text and tables never
drift from the workbook. Narrative judgements live in NARRATIVE below.
"""
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from .assumptions import COMPANIES, MARKET
from .charts import CH, all_charts
from .config import BASE_FY, COVERAGE, OUTPUTS, PROCESSED, fy_label
from .forecast import (base_state, implied_roe, implied_wacc, load, project, sensitivity, sotp,
                       target_price, wacc_inputs)

INK = colors.HexColor("#1B2A3A")
MUTED = colors.HexColor("#6B7785")
RULE = colors.HexColor("#D5DBE2")
BAND = colors.HexColor("#F3F5F8")
ACCENT = colors.HexColor("#1F5F9E")
RATING_COL = {"BUY": colors.HexColor("#2E7D32"), "HOLD": colors.HexColor("#8A6D1F"),
              "SELL": colors.HexColor("#B5532A")}

S = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK),
    "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=10.5, leading=14, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK,
                         spaceBefore=6, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=ACCENT,
                         spaceBefore=6, spaceAfter=2),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.8, leading=12.4, textColor=INK,
                           spaceAfter=5, alignment=TA_LEFT),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=8.8, leading=12.2, textColor=INK,
                             leftIndent=10, bulletIndent=0, spaceAfter=2),
    "quote": ParagraphStyle("quote", fontName="Helvetica-Oblique", fontSize=8.2, leading=11, textColor=MUTED,
                            leftIndent=8, spaceAfter=3),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=7.6, leading=9.4, textColor=INK),
}

def narrative(t: str) -> dict:
    """Company thesis, with every number pulled from the model at build time."""
    tp = target_price(t)
    fc = project(t)
    hist, mkt = load(t)
    b = hist.loc[BASE_FY]
    nd = (fc.borrowings + fc.revolver - fc.cash) / fc.ebitda
    cp = pd.read_csv(PROCESSED / "comps.csv", index_col=0)
    g27 = fc.pat_attr.iloc[0] / b.net_profit - 1
    cagr = (fc.ebitda.iloc[-1] / b.operating_profit) ** (1 / len(fc)) - 1
    if t == "NTPC":
        so = sotp(t)
        parts = list(so["parts"].values())
        roes = {r: sotp(t, r)["per_share"] for r in (0.155, 0.17, 0.18)}
        return {
            "headline": "A fair price for the regulated compounder; the upside needs returns above the rulebook",
            "thesis": [
                f"<b>The build-out is real and mostly regulated.</b> Group capex was Rs 49,068 cr in FY26; management "
                f"guides Rs 1,08,000 cr for FY27 and Rs 5,97,000 cr over FY28-32. At 70% delivery the model commissions "
                f"~{(fc.re_mw.iloc[0] - COMPANIES[t]['re_mw0']) / 1000:.1f} GW of renewables in FY27 (7-8 GW guided) and "
                f"reaches {fc.re_mw.iloc[5] / 1000:.0f} GW by FY32 against the 60 GW target, while regulated equity grows "
                f"from Rs {COMPANIES[t]['regeq0']:,} cr to Rs {fc.regulated_equity.iloc[-1]:,.0f} cr by FY36.",
                f"<b>FY27 profit falls on tax, not operations.</b> FY26 net profit (Rs {b.net_profit:,.0f} cr) included a "
                f"tax credit (reported effective rate -12%, Screener). At a normalised 25% we forecast Rs {fc.pat_attr.iloc[0]:,.0f} cr attributable in "
                f"FY27 ({g27:+.0%}), then {fc.pat_attr.iloc[1] / fc.pat_attr.iloc[0] - 1:.0%} "
                f"growth in FY28.",
                f"<b>HOLD, target Rs {tp['tp']:,.0f}.</b> Sum of the parts at Mar-27: regulated equity valued by residual "
                f"income at {so['pb']:.2f}x book (Rs {parts[0]:,.0f} cr), equity in regulated CWIP at book "
                f"(Rs {parts[1]:,.0f} cr) and the 89% NTPC Green stake at market less 20% (Rs {parts[2]:,.0f} cr). "
                f"Today's price implies NTPC earns {implied_roe(t):.1%} on regulated equity, against 15.5% normative plus "
                f"~0.4 points of net operational gains in FY26. Each extra point of earned RoE is worth ~Rs "
                f"{(roes[0.17] - roes[0.155]) / 1.5:,.0f} a share: 17% gives Rs {roes[0.17]:,.0f}, 18% gives "
                f"Rs {roes[0.18]:,.0f}.",
            ],
            "risks": [f"Upside: sustained incentives and efficiency gains lift earned RoE toward 17-18%.",
                      "Execution slippage beyond the 30% haircut; FY26 RE adds were gated by transmission connectivity.",
                      "Coal additions (~16.5 GW under construction) keep carbon intensity near 1,650 tCO2e per Rs cr.",
                      f"Leverage: net debt/EBITDA peaks at {nd.max():.1f}x and the model draws up to "
                      f"Rs {fc.revolver.max():,.0f} cr of short-term funding before FY32."],
        }
    if t == "TATAPOWER":
        return {
            "headline": "Good businesses, but the price already assumes a cheap cost of capital",
            "thesis": [
                "<b>The growth story is real.</b> Rs 25,000 cr of FY27 capex is lined up (half RE, half FGD and T&amp;D), "
                "Mumbai transmission adds ~Rs 1,000 cr a year and rooftop solar targets Rs 30,000 cr of revenue by 2030. "
                f"The model adds ~{fc.re_mw.iloc[0] / 1000:.1f} GW of RE in FY27 and compounds EBITDA at {cagr:.0%} a year "
                "to FY36.",
                f"<b>The stock prices in more than the plan delivers.</b> At Rs {mkt.price:,.0f} Tata Power trades on "
                f"{cp.loc[t, 'ev_ebitda']:.1f}x FY26A EV/EBITDA and {cp.loc[t, 'pe']:.0f}x trailing earnings. Solving the DCF "
                f"for today's price gives a {implied_wacc(t):.1%} WACC against {tp['wacc']:.1%} on a "
                f"{wacc_inputs(t)['beta']:.2f} Blume-adjusted beta. Management described Q1FY27 profit growth as about 6%; "
                f"we forecast {g27:+.0%} for FY27 as interest and depreciation step up with the build-out.",
                f"<b>SELL, target Rs {tp['tp']:,.0f}</b>: 50% DCF rolled forward 12 months (Rs {tp['dcf_12m']:,.0f}) and "
                f"50% peer EV/EBITDA of {tp['multiple']:.1f}x on FY27E (Rs {tp['relative']:,.0f}). This sits at the low end "
                "of broker targets dated before 14-Aug (Rs 300-485, average Rs 394). The call rests on the cost of "
                "equity; see the sensitivity table.",
            ],
            "risks": ["Upside: rooftop, EPC and manufacturing earnings grow faster than the 4% core drift.",
                      "Associates (coal, Tata Projects) are not modelled separately.",
                      "A lower risk premium for Indian utilities would close most of the gap."],
        }
    return {
        "headline": "On track for 30 GW, and the market already knows",
        "thesis": [
            "<b>Execution is the best in the group.</b> JSW guided 3 GW and Rs 20,000 cr of capex for FY27 and had "
            f"commissioned 1.1 GW by late July; at guided capex the model adds ~{(fc.re_mw.iloc[0] - base_state(t)['mw']) / 1000:.1f} GW "
            "of RE in FY27. Locked-in capacity of 32.1 GW already covers the FY30 target.",
            f"<b>Earnings lag the balance sheet.</b> FY27E EBITDA rises to Rs {fc.ebitda.iloc[0]:,.0f} cr "
            f"({fc.ebitda.iloc[0] / b.operating_profit - 1:+.0%}) as FY26 acquisitions and additions annualise, but interest "
            f"and depreciation follow and FY26 had a tax credit: attributable PAT of Rs {fc.pat_attr.iloc[0]:,.0f} cr "
            f"({g27:+.0%}), in line with Q1FY27's Rs 533 cr.",
            f"<b>HOLD, target Rs {tp['tp']:,.0f} ({tp['upside']:+.1%}, just inside the -10% SELL line)</b>: 12-month DCF "
            f"Rs {tp['dcf_12m']:,.0f} and {tp['multiple']:.1f}x FY27E EV/EBITDA Rs {tp['relative']:,.0f}. The stock's "
            f"run to Rs {mkt.price:,.0f} leaves little room. Net debt/EBITDA peaks at {nd.max():.1f}x in FY27 and falls below "
            f"{nd.iloc[-1]:.0f}x by FY36; the re-rating case needs that de-levering in reported numbers.",
        ],
        "risks": ["Merchant exposure on the thermal fleet and hydrology on the hydro assets.",
                  "Battery and wind-blade manufacturing are early; external orders so far are small (Rs 440 cr).",
                  "Weighted cost of debt of 8.36% leaves little room if the G-sec stays near 7.1%."],
    }


def _tbl(data, widths, header=True, zebra=True, align_right_from=1):
    t = Table(data, colWidths=widths, hAlign="LEFT")
    st = [("FONT", (0, 0), (-1, -1), "Helvetica", 7.6), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
          ("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
          ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE)]
    if header:
        st += [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.6), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK)]
    if zebra:
        st += [("BACKGROUND", (0, r), (-1, r), BAND) for r in range(2, len(data), 2)]
    t.setStyle(TableStyle(st))
    return t


def _img(path, width=175 * mm):
    from PIL import Image as PImage
    w, h = PImage.open(path).size
    return Image(str(path), width=width, height=width * h / w)


def _clean(text: str) -> str:
    """Escape for ReportLab markup; Helvetica has no rupee glyph."""
    from xml.sax.saxutils import escape
    return escape(str(text).replace("\u20b9", "Rs ").replace("  ", " "))


def _fmt(v, kind="num"):
    if pd.isna(v):
        return "-"
    return {"num": f"{v:,.0f}", "pct": f"{v:.1%}", "x": f"{v:.1f}x", "dec": f"{v:,.1f}"}[kind]


def _page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "India Power - initiation of coverage | Student research, not investment advice")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.restoreState()


def summary_table():
    cons = pd.read_csv(PROCESSED / "consensus.csv")
    rows = [["Company", "Rating", "CMP", "Target", "Upside", "Method", "DCF\n12m", "EV/EBITDA\n12m",
             "Mkt-implied\nWACC", "Consensus\ntarget"]]
    for t in COVERAGE:
        tp = target_price(t)
        c = cons[(cons.ticker == t) & (cons.metric == "consensus_tp")].value
        rows.append([COVERAGE[t], tp["rating"], _fmt(tp["price"]), _fmt(tp["tp"]), _fmt(tp["upside"], "pct"),
                     "SOTP" if tp["method"] == "SOTP" else "Blend", _fmt(tp["dcf_12m"]), _fmt(tp["relative"]),
                     _fmt(implied_wacc(t), "pct"), _fmt(float(c.iloc[0])) if len(c) else "-"])
    t = _tbl(rows, [36 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 14 * mm, 18 * mm, 19 * mm, 18 * mm])
    for i, r in enumerate(rows[1:], 1):
        t.setStyle(TableStyle([("TEXTCOLOR", (1, i), (1, i), RATING_COL[r[1]]),
                               ("FONT", (1, i), (1, i), "Helvetica-Bold", 7.6)]))
    return t


def forecast_table(ticker):
    hist, mkt = load(ticker)
    fc = project(ticker)
    yrs = [BASE_FY - 1, BASE_FY] + list(fc.index[:4])
    head = ["Rs crore"] + [fy_label(y, y > BASE_FY) for y in yrs]

    def val(y, h_col, f_col):
        return hist.loc[y, h_col] if y <= BASE_FY else fc.loc[y, f_col]
    lines = [("Revenue", "sales", "sales"), ("EBITDA", "operating_profit", "ebitda"),
             ("  of which renewables", None, "re_ebitda"), ("Net profit to shareholders", "net_profit", "pat_attr"),
             ("Capex", None, "capex"), ("Borrowings incl. revolver", "borrowings", "debt_all"),
             ("Renewable capacity (MW)", None, "re_mw")]
    fc["debt_all"] = fc.borrowings + fc.revolver
    data = [head]
    for lab, hc, fcol in lines:
        row = [lab]
        for y in yrs:
            if y <= BASE_FY and hc is None:
                h = hist
                v = (h.fixed_assets.diff().loc[y] + h.depreciation.loc[y] + h.cwip.diff().loc[y]
                     if fcol == "capex" else float("nan"))
            else:
                v = val(y, hc, fcol)
            row.append(_fmt(v))
        data.append(row)
    eps = ["EPS (Rs)"] + [_fmt(val(y, "net_profit", "pat_attr") / mkt.shares_cr, "dec") for y in yrs]
    pe = ["P/E at CMP"] + [_fmt(mkt.price / (val(y, "net_profit", "pat_attr") / mkt.shares_cr), "x") for y in yrs]
    marg = ["EBITDA margin"] + [_fmt(val(y, "operating_profit", "ebitda") / val(y, "sales", "sales"), "pct") for y in yrs]
    data += [marg, eps, pe]
    return _tbl(data, [34 * mm] + [23 * mm] * len(yrs))


def sens_table(ticker):
    s = sensitivity(ticker)
    data = [["WACC \\ g"] + list(s.columns)] + [[i] + [_fmt(v) for v in r] for i, r in s.iterrows()]
    t = _tbl(data, [22 * mm] + [18 * mm] * len(s.columns), zebra=False)
    t.setStyle(TableStyle([("BACKGROUND", (3, 3), (3, 3), colors.HexColor("#E3ECF6")),
                           ("FONT", (3, 3), (3, 3), "Helvetica-Bold", 7.6)]))
    return t


def wacc_table(ticker):
    w = wacc_inputs(ticker)
    a = COMPANIES[ticker]
    rows = [["Input", "Value"], ["Risk-free (G-sec less default spread)", _fmt(w["rf"], "pct")],
            ["Beta (Blume-adjusted)", f"{w['beta']:.2f}"], ["Equity risk premium", _fmt(MARKET["erp"], "pct")],
            ["Cost of equity", _fmt(w["ke"], "pct")], ["Pre-tax cost of debt", _fmt(w["kd"], "pct")],
            ["Debt weight (market)", _fmt(w["wd"], "pct")], ["WACC", _fmt(w["wacc"], "pct")],
            ["Terminal growth / RONIC", f"{a['g']:.1%} / {a['ronic']:.1%}"]]
    return _tbl(rows, [55 * mm, 22 * mm])


def quotes(ticker, n=4):
    g = pd.read_csv(PROCESSED / "guidance_sentences.csv")
    g = g[(g.ticker == ticker) & g.sentence.str.contains(r"capex|GW|gigawatt|crore", case=False)]
    g = g[g.sentence.str.len() < 260].sort_values("date", ascending=False)
    keys = {"NTPC": ["150 gigawatt", "1,08,000", "5,97,000", "8 GW per annum"],
            "TATAPOWER": ["25,000 crores that we have lined up", "10,000 crores of investment", "30,000 crores of rooftop", "higher than INR 6,000"],
            "JSWENERGY": ["3 GW capacity addition and", "32.1 GW", "8.36%", "1.1 GW of fresh"]}[ticker]
    out = []
    for k in keys:
        m = g[g.sentence.str.contains(k, regex=False)]
        if len(m):
            r = m.iloc[0]
            out.append(Paragraph(f"“{_clean(r.sentence)}”<font color='#6B7785'>[{r.call} call, p{r.page}]</font>",
                                 S["quote"]))
    return out[:n]


def company_section(ticker):
    tp = target_price(ticker)
    n = narrative(ticker)
    col = RATING_COL[tp["rating"]]
    head = Table([[Paragraph(f"<b>{COVERAGE[ticker]}</b>", S["h1"]),
                   Paragraph(f"<font color='{col.hexval()}'><b>{tp['rating']}</b></font>  "
                             f"TP Rs {tp['tp']:,.0f} | CMP Rs {tp['price']:,.1f} | {tp['upside']:+.0%}", S["h2"])]],
                 colWidths=[80 * mm, 95 * mm])
    head.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 1.2, INK), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                              ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    el = [head, Spacer(1, 4), Paragraph(n["headline"], S["sub"]), Spacer(1, 4)]
    el += [Paragraph(p, S["body"]) for p in n["thesis"]]
    el += [Paragraph("What management said", S["h2"])] + quotes(ticker)
    el += [Paragraph("Forecast summary", S["h2"]), forecast_table(ticker), Spacer(1, 4),
           _img(CH / f"{ticker}_earnings.png"), PageBreak()]
    el += [Paragraph(f"{COVERAGE[ticker]}: valuation", S["h1"]), _img(CH / f"{ticker}_football.png", 165 * mm)]
    side = Table([[wacc_table(ticker), sens_table(ticker)]], colWidths=[82 * mm, 95 * mm])
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    el += [Paragraph("Cost of capital and DCF sensitivity (Rs per share, WACC rows x terminal growth)", S["h2"]),
           side, Spacer(1, 4),
           Paragraph(method_text(ticker, tp), S["body"]),
           Paragraph("Key assumptions", S["h2"])]
    el += [Paragraph(f"<b>{k.capitalize()}:</b> {_clean(v)}", S["bullet"], bulletText="•")
           for k, v in COMPANIES[ticker]["rationale"].items()]
    el += [Paragraph("Risks to the call", S["h2"])]
    el += [Paragraph(r, S["bullet"], bulletText="•") for r in n["risks"]]
    el += [KeepTogether([Paragraph("Earnings-call themes (automated transcript analysis)", S["h2"]),
                         _img(CH / f"{ticker}_themes.png", 140 * mm)]), PageBreak()]
    return el


def method_text(ticker, tp):
    if tp["method"] == "SOTP":
        so = sotp(ticker)
        return (f"Target = sum of the parts (Rs {tp['tp']:,.0f}): regulated equity by residual income at "
                f"{so['pb']:.2f}x FY27E book, regulated CWIP equity at book, NTPC Green at market less a 20% holdco "
                f"discount. Cross-checks: 12-month DCF Rs {tp['dcf_12m']:,.0f}, FY27E EV/EBITDA at {tp['multiple']:.1f}x "
                f"Rs {tp['relative']:,.0f}. The DCF sits far below because FCFF stays negative through a decade of "
                f"guided capex (terminal value {tp['tv_share']:.0%} of EV), and a WACC-based DCF ignores that the "
                f"regulator guarantees a return on that capex; the SOTP prices that guarantee directly.")
    return (f"Target = {MARKET['dcf_weight']:.0%} DCF rolled forward 12 months at the cost of equity "
            f"(Rs {tp['dcf_12m']:,.0f}) + {1 - MARKET['dcf_weight']:.0%} peer EV/EBITDA of {tp['multiple']:.1f}x on "
            f"FY27E EBITDA less FY27E net debt (Rs {tp['relative']:,.0f}). Terminal value is {tp['tv_share']:.0%} of "
            f"DCF enterprise value; the value-driver formula ties terminal reinvestment to growth at a "
            f"{COMPANIES[ticker]['ronic']:.1%} return on new capital.")


def comps_table():
    c = pd.read_csv(PROCESSED / "comps.csv", index_col=0).sort_values("mcap_cr", ascending=False)
    data = [["Company", "Segment", "Mcap (Rs cr)", "EV/EBITDA", "P/E", "P/B", "ROE", "EBITDA mgn", "ND/EBITDA"]]
    for _, r in c.iterrows():
        data.append([r["name"], r.segment, _fmt(r.mcap_cr), _fmt(r.ev_ebitda, "x"), _fmt(r.pe, "x"),
                     _fmt(r.pb, "x"), _fmt(r.roe, "pct"), _fmt(r.ebitda_margin, "pct"), _fmt(r.nd_ebitda, "x")])
    return _tbl(data, [33 * mm, 34 * mm, 19 * mm, 16 * mm, 14 * mm, 12 * mm, 13 * mm, 17 * mm, 16 * mm],
                align_right_from=2)


def quarterly_table():
    q = pd.read_csv(PROCESSED / "quarterly.csv")
    q = q.sort_values("quarter_end").groupby("ticker").tail(3)
    data = [["Company", "Quarter ended", "Revenue", "EBITDA", "Net profit"]]
    for _, r in q.iterrows():
        data.append([COVERAGE[r.ticker], r.quarter_end, _fmt(r.revenue), _fmt(r.ebitda), _fmt(r.pat)])
    return _tbl(data, [40 * mm, 26 * mm, 24 * mm, 24 * mm, 24 * mm], align_right_from=2)


def build(author: str = "Atharva Akhanzode") -> str:
    all_charts()
    path = OUTPUTS / "India_Power_Initiation.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title="India Power: Initiation of Coverage", author=author)
    _, mkt = load("NTPC")
    el = [Paragraph("India Power", S["title"]),
          Paragraph("Initiation of coverage: the build-out is financed, the returns are not all priced the same",
                    S["sub"]),
          Spacer(1, 3),
          Paragraph(f"{author} | Data as of {pd.Timestamp(mkt.price_date):%d %b %Y}", S["small"]),
          Spacer(1, 8), summary_table(), Spacer(1, 8),
          Paragraph("Investment summary", S["h1"]),
          Paragraph("India's power sector is in its largest investment cycle in a decade. Listed generators and "
                    "utilities spent roughly Rs 2.2 lakh crore on assets in FY26, more than double FY23, and the "
                    "three companies we initiate on have guided to spend more in FY27. Peak demand touched 270 GW "
                    "in July 2026 (JSW Energy, Q1FY27 call), against the 250 GW record of May 2024.", S["body"]),
          Paragraph("Capex starts from management guidance, haircut for execution, and is turned into capacity. "
                    "Renewables earn MW x utilisation x tariff; NTPC's regulated EBITDA scales with regulated "
                    "equity, which grows by 30% of the regulated assets commissioned; Tata Power's and JSW's other "
                    "assets earn a yield calibrated on FY19-26. At guided capex the model commissions roughly what "
                    "each company has guided for FY27. On that basis none of the three is cheap: the market is "
                    "already paying for the build-out.", S["body"])]
    for t in COVERAGE:
        tp = target_price(t)
        el.append(Paragraph(f"<b>{COVERAGE[t]} - {tp['rating']}, TP Rs {tp['tp']:,.0f} ({tp['upside']:+.0%}).</b> "
                            f"{narrative(t)['headline']}.", S["bullet"], bulletText="•"))
    el += [Spacer(1, 6), _img(CH / "sector_capex.png", 165 * mm), PageBreak(),
           Paragraph("Sector: capacity, capital and carbon", S["h1"]),
           Paragraph("Three facts frame the sector. First, the grid is short of firm capacity: the CEA projects an "
                     "additional 86 GW of coal requirement to 2036, of which 68 GW is in the pipeline (NTPC, "
                     "Q4FY26 call), even as India crossed 50% non-fossil installed capacity in June 2025. Second, "
                     "the capital is being raised on balance sheets that are already levered 4-7x net debt/EBITDA. "
                     "Third, the market does not price these assets uniformly: hydro and pure renewables trade at "
                     "16-32x EBITDA, integrated thermal-led names at 10-15x.", S["body"]),
           _img(CH / "comps_scatter.png", 165 * mm), Spacer(1, 4),
           Paragraph(f"Listed power comparables (FY26A, prices {mkt.price_date})", S["h2"]), comps_table(),
           PageBreak(),
           Paragraph("Carbon exposure from BRSR filings", S["h1"]),
           Paragraph("We compute scope 1+2 emissions per rupee crore of revenue from SEBI's mandatory BRSR "
                     "disclosures. Filers mix units (tonnes, million tonnes, kilograms), so rows that sit more than "
                     "5x away from a company's own median, or thermal generators reporting under 50 t per Rs "
                     "crore, are flagged and excluded rather than rescaled. The spread is wide enough to matter "
                     "for cost of capital as lenders price transition risk.", S["body"]),
           _img(CH / "carbon_intensity.png", 165 * mm), Spacer(1, 6),
           Paragraph("Latest reported quarters", S["h2"]), quarterly_table(),
           Paragraph("Source: Yahoo Finance quarterly statements; quarters missing from that feed are omitted.",
                     S["small"]), PageBreak()]
    for t in COVERAGE:
        el += company_section(t)
    el += [Paragraph("Methodology and sources", S["h1"])]
    method = [
        "<b>Financials:</b> consolidated annual statements FY14-FY26 (Screener export, cross-checked line by line "
        "against screener.in; FY26 revenue, EBITDA, PAT and borrowings match exactly).",
        "<b>Guidance:</b> 23 earnings-call transcripts (Q2FY25-Q1FY27) downloaded from NSE corporate filings. A rule-"
        "based extractor keeps every sentence pairing a forward-looking cue with a figure and unit; each capex "
        "input in the model cites the call and page it came from.",
        "<b>Model:</b> Excel workbook per company with live formulas (inputs in blue). A test suite recalculates "
        "the workbook with the <i>formulas</i> package and checks WACC, DCF, peer value, target and rating "
        "against the Python engine.",
        "<b>Cost of capital:</b> 10Y G-sec 6.76% (close 14-Aug-2026, Investing.com) less Damodaran's 1.87% India "
        "default spread; total ERP 7.08% (Damodaran, Jan-2026); Blume-adjusted 2-year weekly betas vs Nifty 50.",
        "<b>Consensus:</b> average of the latest broker targets dated on or before 14-Aug-2026 (Investing.com; "
        "8 brokers each for NTPC and Tata Power) and Yahoo Finance's 21-Jul-2026 average for JSW Energy.",
        "<b>Cut-off:</b> all market data, consensus and transcripts are as of 14-Aug-2026 (last call used: "
        "NTPC Q1FY27, filed 2-Aug-2026).",
    ]
    el += [Paragraph(m, S["bullet"], bulletText="•") for m in method]
    el += [Spacer(1, 8), Paragraph(
        "Disclaimer: prepared as a student research exercise. It is not investment advice or a recommendation to "
        "buy or sell any security. Ratings: BUY above +15% to target, SELL below -10%, HOLD in between.", S["small"])]
    doc.build(el, onFirstPage=_page, onLaterPages=_page)
    return str(path)


if __name__ == "__main__":
    print(build())
