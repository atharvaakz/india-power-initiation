"""The Excel workbook and the Python engine must agree.

The `formulas` package recalculates every formula in the saved workbook without
Excel, so this catches any row reference that drifted from forecast.py.
Run: PYTHONPATH=src python3 -m pytest -q
"""
from pathlib import Path

import formulas
import openpyxl
import pytest

from powerinit.config import COVERAGE
from powerinit.forecast import dcf, project, target_price
from powerinit.model_excel import build


@pytest.fixture(scope="module", params=list(COVERAGE))
def case(request):
    t = request.param
    path = Path(build(t))
    solution = formulas.ExcelModel().loads(str(path)).finish().calculate()
    values = {k.upper(): v for k, v in solution.items()}
    names = openpyxl.load_workbook(path).defined_names

    def named(n):
        sheet, addr = names[n].attr_text.replace("$", "").split("!")
        key = f"'[{path.name.upper()}]{sheet.upper()}'!{addr}"
        return values[key].value[0, 0]

    return t, named


def test_balance_sheet_balances(case):
    t, _ = case
    assert project(t).check.abs().max() < 1e-6


def test_excel_matches_python(case):
    t, named = case
    tp = target_price(t)
    assert named("wacc") == pytest.approx(tp["wacc"], rel=1e-9)
    assert named("out_dcf_ps") == pytest.approx(tp["dcf"], rel=1e-6)
    assert named("out_rel_ps") == pytest.approx(tp["relative"], rel=1e-6)
    assert named("out_tp") == pytest.approx(tp["tp"], rel=1e-6)
    assert named("out_rating") == tp["rating"]


def test_terminal_value_is_bounded(case):
    t, _ = case
    # Build-out years have negative FCFF, so TV can exceed EV, but not absurdly.
    assert 0.5 < dcf(t).tv_share < 1.5
