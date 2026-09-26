# India Power: initiation of coverage

Sell-side style equity research on three listed Indian power companies, built as a reproducible pipeline: data, earnings-call guidance extraction, a three-statement model in Excel with live formulas, valuation, and a PDF report.

| Company | Rating | CMP (Rs) | Target (Rs) | Upside | Consensus target |
|---|---|---|---|---|---|
| NTPC | HOLD | 336 | 314 | -7% | 447 |
| Tata Power | SELL | 382 | 331 | -13% | 394 |
| JSW Energy | HOLD | 560 | 506 | -10% | 619 |

Data as of 14-Aug-2026 (prices, betas, G-sec yield, consensus, transcripts up to Q1FY27). Student research exercise, not investment advice.

**Outputs**
- `outputs/India_Power_Initiation.pdf`: 12-page initiation report (sector primer, comps, BRSR carbon intensity, three company notes)
- `outputs/<TICKER>_model.xlsx`: model per company. Inputs are blue; everything else is a formula, so changing an input moves the target price.

## How it works

```
data.py          consolidated FY14-FY26 financials, market data, BRSR emissions  ->  data/processed/*.csv
transcripts.py   23 earnings calls from NSE filings -> guidance sentences + theme counts
quarterly.py     latest reported quarters
comps.py         14-company trading comps, peer EV/EBITDA
assumptions.py   every forecast input, with the call and page it comes from
forecast.py      three-statement forecast, DCF, blended target, reverse DCF (reference implementation)
model_excel.py   the same logic written as Excel formulas
charts.py / report.py
tests/           recalculates each workbook and checks it matches forecast.py
```

**Forecast logic (model v2).** Capex starts from management guidance, is haircut for execution, and flows through capital work in progress. The share commissioned each year becomes capacity:
- **Renewables:** MW added = RE share of assets commissioned / cost per MW. EBITDA = MW x capacity utilisation x 8,760 h x tariff x margin, calibrated to NTPC Green's FY26 generation and revenue. At guided capex the model commissions ~7 GW (NTPC) and ~3 GW (JSW) in FY27, matching guidance.
- **NTPC regulated business:** regulated equity grows by 30% of regulated assets commissioned, and regulated EBITDA scales with it (CERC cost-plus).
- **Tata Power and JSW core:** existing EBITDA drifts, and non-RE assets commissioned earn a yield calibrated on FY19-26.

Revenue follows from each engine's margin. JV profit is equity-accounted and retained. Minority interests are carried separately, and EPS is on attributable profit. A revolver keeps cash at or above zero; its interest is charged on the opening balance, so there is no circularity. The balance sheet balances every year to FY36.

**Valuation (12-month targets).**
- *NTPC:* sum of the parts. Regulated equity is valued by residual income on the model's regulated-equity path (15.9% earned RoE vs cost of equity), plus regulated CWIP equity at book and the 89% NTPC Green stake at market less a 20% holdco discount. The market price implies a 16.8% earned RoE.
- *Tata Power and JSW:* 50% DCF rolled forward at the cost of equity, 50% peer-median EV/EBITDA on FY27E EBITDA less FY27E net debt.
- *Cost of capital:* the 10Y G-sec (6.76%, 14-Aug-2026) less Damodaran's India default spread (1.87%), a 7.08% ERP, and Blume-adjusted betas.
- *Cross-checks:* a reverse DCF gives the WACC implied by today's price.

## Run it

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m powerinit models   # rebuild workbooks from committed data
PYTHONPATH=src python -m powerinit report   # rebuild charts + PDF
PYTHONPATH=src python -m pytest -q          # Excel vs Python check
```

`python -m powerinit data` and `transcripts` refresh inputs from the network. They also need the raw BRSR research workspace (set `POWERINIT_RAW` to the folder that holds `Aditya_Stata/` and `brsr_toolkit/`).

## Sources

- Financials: Screener export, cross-checked against screener.in (FY26 matches exactly)
- Guidance: earnings-call transcripts on NSE
- Prices and betas: NSE via yfinance
- Emissions: SEBI BRSR filings
- G-sec yield: Investing.com historical data (14-Aug-2026 close)
- ERP and default spread: Damodaran (Jan-2026)
- Consensus: latest broker targets dated on or before 14-Aug-2026 (Investing.com), Yahoo Finance (JSW, 21-Jul-2026)

## Notes

Known simplifications:
- Tata Power's associates (coal, Tata Projects) are not modelled separately, and its asset-light businesses (rooftop, EPC, manufacturing) only enter through a flat EBITDA drift.
- The RE tariff and utilisation are single blended figures per company, not per project.
- NTPC's FY33-36 capex is held at the FY28-32 run-rate rather than the nuclear-heavy FY33-37 guidance.
