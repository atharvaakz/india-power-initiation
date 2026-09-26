"""The Excel workbook and the Python engine must agree.

The `formulas` package recalculates every formula in the saved workbook without
Excel, so this catches any row reference that drifted from forecast.py.
Run: PYTHONPATH=src python3 -m pytest -q
"""
from pathlib import Path

import formulas
import openpyxl
import pytest

from powerinit.assumptions import COMPANIES, MARKET
from powerinit.config import COVERAGE
from powerinit.forecast import base_state, dcf, project, sotp, target_price
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
    assert named("out_dcf_12m") == pytest.approx(tp["dcf_12m"], rel=1e-6)
    assert named("out_rel_ps") == pytest.approx(tp["relative"], rel=1e-6)
    if COMPANIES[t]["regulated"]:
        assert named("out_sotp_ps") == pytest.approx(sotp(t)["per_share"], rel=1e-6)
    assert named("out_tp") == pytest.approx(tp["tp"], rel=1e-6)
    assert named("out_rating") == tp["rating"]


def test_cash_never_below_floor(case):
    t, _ = case
    fc = project(t)
    assert (fc.cash >= MARKET["min_cash"] - 1e-9).all()
    assert (fc.revolver >= -1e-9).all()


def test_capacity_build_matches_guidance():
    """At guided capex the model should commission roughly what management guided for FY27."""
    assert 6000 < project("NTPC").re_mw.iloc[0] - base_state("NTPC")["mw"] < 8500          # 7-8 GW RE guided
    assert 2400 < project("JSWENERGY").re_mw.iloc[0] - base_state("JSWENERGY")["mw"] < 3300  # ~3 GW guided


def test_terminal_value_is_bounded(case):
    t, _ = case
    # Build-out years have negative FCFF, so TV can exceed EV, but not absurdly.
    assert 0.5 < dcf(t).tv_share < 1.5
