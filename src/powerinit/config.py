"""Paths, universe and constants shared across the pipeline."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
TRANSCRIPTS = DATA / "transcripts"
OUTPUTS = ROOT / "outputs"

# Raw inputs live in the BRSR research workspace (not committed; ~35 GB).
# Override with POWERINIT_RAW=/path/to/projects if the layout differs.
RAW_ROOT = Path(os.environ.get("POWERINIT_RAW", ROOT.parent))
SCREENER_DTA = RAW_ROOT / "Aditya_Stata/data/04_screener_financials.dta"
MASTER_PANEL = RAW_ROOT / "Aditya_Stata/MASTER_PANEL.csv"
XBRL_RESULTS = RAW_ROOT / "brsr_toolkit/data/structured_financial_results_xbrl.csv"

# Companies with full models and a rating.
COVERAGE = {
    "NTPC": "NTPC Ltd",
    "TATAPOWER": "Tata Power Company Ltd",
    "JSWENERGY": "JSW Energy Ltd",
}

# Listed power peers used for comps and the sector primer.
UNIVERSE = {
    "NTPC": ("NTPC Ltd", "Integrated / thermal-led"),
    "TATAPOWER": ("Tata Power", "Integrated / private"),
    "JSWENERGY": ("JSW Energy", "IPP / private"),
    "ADANIPOWER": ("Adani Power", "IPP / thermal"),
    "TORNTPOWER": ("Torrent Power", "Integrated / private"),
    "CESC": ("CESC", "Integrated / private"),
    "NHPC": ("NHPC", "Hydro / PSU"),
    "SJVN": ("SJVN", "Hydro / PSU"),
    "NLCINDIA": ("NLC India", "Lignite-thermal / PSU"),
    "POWERGRID": ("Power Grid Corp", "Transmission / PSU"),
    "ADANIGREEN": ("Adani Green Energy", "Renewables"),
    "RPOWER": ("Reliance Power", "IPP / thermal"),
    "JPPOWER": ("JP Power Ventures", "IPP / thermal"),
    "PTC": ("PTC India", "Power trading"),
}

# Data cut-off: every market-dated input (prices, betas, yields, consensus) is as of this close.
ASOF = "2026-08-14"

# Fiscal-year convention: the source data labels FY2025-26 (ended Mar-2026) as 2025.
BASE_FY = 2025          # last reported year = FY26A
N_FORECAST = 10         # FY27E .. FY36E


def fy_label(fy: int, estimate: bool = False) -> str:
    """2025 -> 'FY26A', 2026 -> 'FY27E'."""
    return f"FY{(fy + 1) % 100:02d}{'E' if estimate else 'A'}"
