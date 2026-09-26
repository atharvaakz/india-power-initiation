"""Earnings-call transcripts: fetch from NSE, extract text, pull guidance.

Guidance extraction is deliberately rule-based: every sentence that pairs a
forward-looking cue with a number and a unit (GW, MW, Rs crore, %, PLF) is kept
with its source call and page, so every forecast input can be traced back to
what management actually said. An optional LLM pass (ANTHROPIC_API_KEY) writes a
short per-call digest on top of the extracted text; nothing downstream needs it.
"""
import json
import os
import re
import time
from datetime import datetime, timedelta

import fitz  # PyMuPDF
import pandas as pd
import requests

from .config import COVERAGE, PROCESSED, TRANSCRIPTS

NSE = "https://www.nseindia.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "*/*",
                      "Referer": f"{NSE}/companies-listing/corporate-filings-announcements"})
    s.get(NSE, timeout=25)  # NSE only serves the API to a session holding its cookies
    time.sleep(1)
    return s


def list_transcripts(s: requests.Session, symbol: str, years: int = 3) -> pd.DataFrame:
    to = datetime.today()
    params = {"index": "equities", "symbol": symbol,
              "from_date": (to - timedelta(days=365 * years)).strftime("%d-%m-%Y"),
              "to_date": to.strftime("%d-%m-%Y")}
    recs = s.get(f"{NSE}/api/corporate-announcements", params=params, timeout=30).json()
    rows = [{"ticker": symbol, "date": pd.to_datetime(r["an_dt"], format="%d-%b-%Y %H:%M:%S"),
             "headline": r.get("attchmntText", ""), "url": r.get("attchmntFile", "")}
            for r in recs
            if "transcript" in (r.get("desc", "") + r.get("attchmntText", "")).lower()
            and str(r.get("attchmntFile", "")).lower().endswith(".pdf")]
    return pd.DataFrame(rows).sort_values("date", ascending=False)


def fetch(n_calls: int = 8) -> pd.DataFrame:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    s = _session()
    got = []
    for sym in COVERAGE:
        for r in list_transcripts(s, sym).head(n_calls).itertuples():
            path = TRANSCRIPTS / f"{sym}_{r.date:%Y-%m-%d}.pdf"
            if not path.exists():
                path.write_bytes(s.get(r.url, timeout=60).content)
                time.sleep(1)
            got.append({"ticker": sym, "date": r.date.date(), "file": path.name, "url": r.url})
    idx = pd.DataFrame(got)
    idx.to_csv(TRANSCRIPTS / "index.csv", index=False)
    return idx


def call_quarter(d) -> str:
    """Results calls happen the month after quarter end: Jul/Aug call -> Q1 of that FY."""
    d = pd.Timestamp(d)
    q_end = (d - pd.offsets.QuarterEnd(1)) if d.month not in (3, 6, 9, 12) else d - pd.offsets.QuarterEnd(1)
    fy = q_end.year + 1 if q_end.month > 3 else q_end.year
    q = {6: 1, 9: 2, 12: 3, 3: 4}[q_end.month]
    return f"Q{q}FY{fy % 100:02d}"


# --- guidance extraction -----------------------------------------------------

FORWARD = re.compile(r"\b(target|guid|plan|expect|by (?:fy|20)\d{2}|pipeline|under construction|"
                     r"will (?:be|add|commission|reach)|commission|capex|we intend|aim|going forward|"
                     r"next (?:year|two|three|few)|outlook|envisag)", re.I)
NUMBER_UNIT = re.compile(r"(\d[\d,\.]*\s*(?:gw|gigawatt|mw|megawatt|gwh|crore|cr\b|lakh crore|"
                         r"%|percent|bu\b|billion units|mtpa))", re.I)
THEMES = {
    "thermal": r"\b(thermal|coal|lignite)\b",
    "renewables": r"\b(renewable|solar|wind|hybrid|\bre\b)",
    "storage": r"\b(storage|bess|battery|pumped)\b",
    "hydro": r"\bhydro\b",
    "nuclear": r"\bnuclear\b",
    "transmission": r"\btransmission\b",
    "distribution": r"\b(distribution|discom|smart meter)",
    "green_hydrogen": r"\b(green hydrogen|electrolys)",
    "rooftop": r"\brooftop\b",
    "manufacturing": r"\b(cell|module|wafer) (manufactur|plant|capacity)",
}


def pdf_pages(path) -> list[str]:
    with fitz.open(path) as doc:
        return [re.sub(r"\s+", " ", p.get_text()) for p in doc]


def extract(idx: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = idx if idx is not None else pd.read_csv(TRANSCRIPTS / "index.csv")
    guidance, themes = [], []
    for r in idx.itertuples():
        pages = pdf_pages(TRANSCRIPTS / r.file)
        text = " ".join(pages)
        q = call_quarter(r.date)
        themes.append({"ticker": r.ticker, "call": q, "date": r.date, "words": len(text.split()),
                       **{k: len(re.findall(v, text, re.I)) for k, v in THEMES.items()}})
        for pno, page in enumerate(pages, 1):
            for sent in re.split(r"(?<=[\.\?!])\s+", page):
                if 40 < len(sent) < 600 and FORWARD.search(sent) and NUMBER_UNIT.search(sent):
                    guidance.append({"ticker": r.ticker, "call": q, "date": r.date, "page": pno,
                                     "figures": "; ".join(m.strip() for m in NUMBER_UNIT.findall(sent)),
                                     "sentence": sent.strip()})
    g = pd.DataFrame(guidance).drop_duplicates(["ticker", "sentence"])
    t = pd.DataFrame(themes).sort_values(["ticker", "date"])
    g.to_csv(PROCESSED / "guidance_sentences.csv", index=False)
    t.to_csv(PROCESSED / "transcript_themes.csv", index=False)
    return g, t


def llm_digest(model: str = "claude-sonnet-5") -> None:
    """Optional: one-paragraph digest per call. Skipped without an API key."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY not set - skipping LLM digests")
        return
    idx = pd.read_csv(TRANSCRIPTS / "index.csv")
    out = {}
    for r in idx.itertuples():
        text = " ".join(pdf_pages(TRANSCRIPTS / r.file))[:120_000]
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 700, "messages": [{"role": "user", "content":
                  "Summarise this Indian power-company earnings call for an equity analyst in 5 bullets: "
                  "capacity guidance, capex, tariffs/PLF, balance sheet, risks. Quote numbers exactly.\n\n" + text}]},
            timeout=120)
        out[r.file] = resp.json()["content"][0]["text"]
    (PROCESSED / "call_digests.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    idx = fetch()
    print(idx)
    g, t = extract(idx)
    print(t.to_string())
    print(g.groupby("ticker").size())
