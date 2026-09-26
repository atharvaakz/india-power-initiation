"""Trading comparables for the listed Indian power universe (FY26A basis)."""
import pandas as pd

from .config import BASE_FY, PROCESSED, UNIVERSE


def build() -> pd.DataFrame:
    f = pd.read_csv(PROCESSED / "fundamentals.csv")
    m = pd.read_csv(PROCESSED / "market.csv").set_index("ticker")
    cur = f[f.fy == BASE_FY].set_index("ticker")
    prv = f[f.fy == BASE_FY - 1].set_index("ticker")
    c = pd.DataFrame(index=cur.index)
    c["name"] = [UNIVERSE[t][0] for t in c.index]
    c["segment"] = [UNIVERSE[t][1] for t in c.index]
    c["price"] = m.price
    c["mcap_cr"] = m.mcap_cr
    c["net_debt_cr"] = cur.borrowings - m.cash_cr
    c["ev_cr"] = c.mcap_cr + c.net_debt_cr + m.minority_cr
    c["sales_growth"] = cur.sales / prv.sales - 1
    c["ebitda_margin"] = cur.operating_profit / cur.sales
    c["ev_ebitda"] = c.ev_cr / cur.operating_profit
    c["pe"] = c.mcap_cr / cur.net_profit
    c["pb"] = c.mcap_cr / (cur.equity_capital + cur.reserves)
    c["roe"] = cur.net_profit / ((cur.equity_capital + cur.reserves + prv.equity_capital + prv.reserves) / 2)
    c["nd_ebitda"] = c.net_debt_cr / cur.operating_profit
    c["div_yield_proxy"] = None
    c = c.drop(columns="div_yield_proxy")
    # Loss-makers and negative-equity names make multiples meaningless.
    c.loc[c.pe <= 0, "pe"] = float("nan")
    c.to_csv(PROCESSED / "comps.csv")
    return c


PEER_SETS = {
    "NTPC": ["NTPC", "NHPC", "SJVN", "NLCINDIA", "POWERGRID"],           # PSU / regulated
    "TATAPOWER": ["TATAPOWER", "TORNTPOWER", "CESC", "JSWENERGY", "ADANIPOWER"],  # private integrated
    # Adani Green (30x) is excluded: a pure RE developer's multiple prices development optionality
    # that an integrated IPP's EBITDA base does not carry.
    "JSWENERGY": ["JSWENERGY", "TATAPOWER", "ADANIPOWER", "TORNTPOWER", "NTPC"],
}


def peer_multiple(ticker: str, comps: pd.DataFrame | None = None) -> float:
    """Median FY26A EV/EBITDA of the peer set, excluding the company itself."""
    c = comps if comps is not None else pd.read_csv(PROCESSED / "comps.csv", index_col=0)
    peers = [p for p in PEER_SETS[ticker] if p != ticker]
    return float(c.loc[peers, "ev_ebitda"].median())


if __name__ == "__main__":
    c = build()
    pd.set_option("display.width", 200)
    print(c.drop(columns=["name"]).round(2).sort_values("mcap_cr", ascending=False).to_string())
    for t in PEER_SETS:
        print(t, "peer EV/EBITDA", round(peer_multiple(t, c), 1))
