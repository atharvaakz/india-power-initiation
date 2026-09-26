"""python -m powerinit [all|data|transcripts|models|report]

`data` and `transcripts` need network access and the raw BRSR workspace;
`models` and `report` run offline from the committed CSVs in data/processed.
"""
import sys

from . import comps, data, model_excel, quarterly, report, transcripts
from .config import COVERAGE, PROCESSED


def main(step: str = "all") -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if step in ("all", "data"):
        data.build_fundamentals()
        data.build_esg()
        data.build_market()
        quarterly.build()
    if step in ("all", "transcripts"):
        transcripts.extract(transcripts.fetch())
    if step in ("all", "data", "models"):
        comps.build()
    if step in ("all", "models"):
        for t in COVERAGE:
            print(model_excel.build(t))
    if step in ("all", "report"):
        print(report.build())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
