"""Latest quarterly results for the covered companies (Yahoo Finance quarterly statements)."""
import pandas as pd

from .config import COVERAGE, PROCESSED

CR = 1e7
ROWS = {"Total Revenue": "revenue", "EBITDA": "ebitda", "Net Income": "pat"}


def build() -> pd.DataFrame:
    import yfinance as yf

    out = []
    for t in COVERAGE:
        q = yf.Ticker(f"{t}.NS").quarterly_income_stmt
        for label, key in ROWS.items():
            if label not in q.index:
                continue
            for d, v in q.loc[label].dropna().items():
                out.append({"ticker": t, "quarter_end": d.date(), "item": key, "value_cr": v / CR})
    df = pd.DataFrame(out).pivot_table(index=["ticker", "quarter_end"], columns="item", values="value_cr")
    df = df.reset_index().sort_values(["ticker", "quarter_end"])
    df.to_csv(PROCESSED / "quarterly.csv", index=False)
    return df


if __name__ == "__main__":
    print(build().round(0).to_string())
