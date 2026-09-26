# India Power: initiation of coverage

Sell-side style equity research on three listed Indian power companies, built as a reproducible pipeline: data, earnings-call guidance extraction, a three-statement model in Excel with live formulas, valuation, and a PDF report.

| Company | Rating | CMP (Rs) | Target (Rs) | Upside | Consensus target |
|---|---|---|---|---|---|
| NTPC | BUY | 327 | 441 | +35% | 430 |
| Tata Power | SELL | 368 | 275 | -25% | 414 |
| JSW Energy | HOLD | 507 | 530 | +5% | 616 |

Prices as of 25-Sep-2026. Student research exercise, not investment advice.

**Outputs**
- `outputs/India_Power_Initiation.pdf`: 10-page initiation report (sector primer, comps, BRSR carbon intensity, three company notes)
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

**Forecast logic.** Capex starts from management guidance and is haircut for execution. Capex flows into capital work in progress; a share is commissioned each year, and commissioned assets earn an EBITDA yield calibrated on each company's FY19-26 history (NTPC 14%, Tata Power 12%, JSW Energy 15%). Revenue follows from EBITDA and a margin path. New debt funds a fixed share of capex; cash is the balancing item, and the balance sheet balances every year.

**Valuation.** The target is 50% FCFF DCF and 50% peer-median EV/EBITDA.
- *Cost of capital:* the INR risk-free rate is the 10Y G-sec (7.11%) minus Damodaran's India default spread (1.87%). The ERP is 7.08% and betas are Blume-adjusted.
- *Terminal value:* the value-driver formula, NOPAT x (1 - g/RONIC) / (WACC - g).
- *Reverse DCF:* solves for the WACC that justifies today's price. It anchors the Tata Power call, where the market price implies 8.6% against our 10.2%.

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
- G-sec yield: Trading Economics
- ERP and default spread: Damodaran (Jan-2026)
- Consensus: Trendlyne and Investing.com

## Notes

Known simplifications:
- Minority share of profit is not split out of net profit.
- JV holdings are valued at book.
- Tata Power's asset-light businesses (rooftop, EPC, manufacturing) are captured only through a flat EBITDA drift.
