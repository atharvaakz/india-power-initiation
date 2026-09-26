"""Forecast and valuation inputs for the three covered companies.

Every capex figure starts from management guidance in the earnings calls
(see data/processed/guidance_sentences.csv for the exact quotes) and is then
haircut by an execution factor based on how much of past guidance was delivered.
EBITDA is driven by assets commissioned (CWIP transfers) times an EBITDA yield
calibrated on FY19-26 history; revenue follows from the margin path.
Years run FY27E..FY33E.
"""

MARKET = {
    # India 10Y G-sec, 25-Sep-2026 (Trading Economics); Damodaran Jan-2026 India
    # default spread 1.87% and total ERP 7.08%. The local risk-free rate strips
    # the default spread so country risk is not counted twice.
    "gsec_10y": 0.0711,
    "default_spread": 0.0187,
    "erp": 0.0708,
    "tax": 0.25,
    "valuation_date": "2026-09-25",
    "stub": 0.51,          # fraction of FY27 remaining after the valuation date
    "dcf_weight": 0.5,     # target price = 50% DCF + 50% peer EV/EBITDA
}

COMPANIES = {
    "NTPC": {
        "rationale": {
            "capex": "Q1FY27 call: group capex Rs 1,08,000 cr for FY27; Rs 5,97,000 cr over FY28-32 "
                     "(Rs 1,19,400 cr/yr). FY26 actual was Rs 49,068 cr, so a 2.2x step-up is "
                     "assumed to be delivered at 70%.",
            "growth": "EBITDA grows with commissioned assets: ~90 GW commercial today, 150 GW targeted by "
                      "FY32. Revenue is backed out from EBITDA and the margin path.",
            "margin": "RE EBITDA margins run far above thermal; mix shift adds ~0.5pp a year.",
            "terminal": "Regulated return on equity 15.5% (CMD, Q1FY27); RONIC set at 12% on total capital.",
        },
        "base_drift": 0.00,       # EBITDA growth of the existing fleet (ageing thermal, flat tariffs)
        "asset_yield": 0.14,      # EBITDA per Rs of assets commissioned; history FY19-26 = 13.8%
        "ebitda_margin": [0.300, 0.305, 0.310, 0.315, 0.320, 0.325, 0.330],
        "capex_guided": [108000, 119400, 119400, 119400, 119400, 119400, 110000],
        "execution": 0.70,
        "other_income_pct": 0.025,
        "dep_rate": 0.070,        # depreciation / opening net block
        "capitalisation": 0.40,   # share of (opening CWIP + capex) commissioned in the year
        "debt_share": 0.50,       # share of capex funded by new borrowing
        "int_rate": 0.055,        # interest / average debt (net of capitalised interest)
        "payout": 0.32,         # FY26 actual 32% (Screener)
        "oa_pct": 0.70, "ol_pct": 0.45,   # non-cash other assets / liabilities as % of sales
        "inv_growth": 0.05,
        "kd": 0.074, "rf_spread_note": "AAA PSU",
        "g": 0.05, "ronic": 0.12,
    },
    "TATAPOWER": {
        "rationale": {
            "capex": "Q1FY27 call: Rs 25,000 cr lined up for FY27 (50% RE, rest FGD and T&D), 'similar "
                     "outlay going forward'. FY26 spend of ~Rs 15,600 cr against ~Rs 22,000 cr guided "
                     "implies ~70-75% delivery; 75% assumed.",
            "growth": "FY26 revenue fell 4.7%; recovery driven by RE IPP, rooftop solar (Rs 30,000 cr "
                      "rooftop revenue ambition by 2030) and Mumbai transmission (~Rs 10,000 cr over 5 yrs).",
            "margin": "Regulated T&D plus RE mix lifts margin from 21% toward 26%.",
            "consensus": "Consensus FY27 PAT growth ~24% (Trendlyne) vs management's 'about 6%' pace in "
                         "Q1FY27; the model sits between at ~12%.",
            "terminal": "Blend of regulated T&D and contracted RE; RONIC 11%.",
        },
        "base_drift": 0.04,       # regulated T&D (~2%) plus asset-light rooftop/EPC growth; Q1FY27 PAT +6% YoY
        "asset_yield": 0.12,      # history FY19-26 = 12.2%
        "ebitda_margin": [0.220, 0.230, 0.240, 0.245, 0.250, 0.255, 0.260],
        "capex_guided": [25000, 25000, 25000, 25000, 25000, 25000, 25000],
        "execution": 0.75,
        "other_income_pct": 0.05,
        "dep_rate": 0.061,
        "capitalisation": 0.50,
        "debt_share": 0.60,
        "int_rate": 0.076,
        "payout": 0.21,         # FY26 actual 21%
        "oa_pct": 0.90, "ol_pct": 0.94,
        "inv_growth": 0.05,
        "kd": 0.080, "rf_spread_note": "AA+ private",
        "g": 0.05, "ronic": 0.11,
    },
    "JSWENERGY": {
        "rationale": {
            "capex": "Q4FY26 and Q1FY27 calls: ~Rs 20,000 cr capex and 3 GW additions in FY27, 1.1 GW "
                     "already commissioned by July; target 30 GW generation by FY30 (32.1 GW locked in). "
                     "Rs 22,000 cr/yr assumed to FY30, tapering after; 90% execution given the Q1 run-rate.",
            "growth": "FY26 revenue +61% on the O2 Power and KSK Mahanadi acquisitions; organic growth "
                      "from 3 GW/yr additions fades as the FY30 target is reached.",
            "margin": "Contracted RE and the 25-yr Utkal PPA hold margins near 50%.",
            "terminal": "Cost of debt 8.36% (Q4FY26); RONIC 11.5%.",
        },
        "base_drift": 0.01,
        "asset_yield": 0.15,      # history FY19-26 = 16.1%, flattered by acquisitions
        "ebitda_margin": [0.500, 0.505, 0.510, 0.515, 0.515, 0.515, 0.515],
        "capex_guided": [20000, 22000, 22000, 22000, 15000, 15000, 15000],
        "execution": 0.90,
        "other_income_pct": 0.05,
        "dep_rate": 0.060,
        "capitalisation": 0.55,
        "debt_share": 0.65,
        "int_rate": 0.084,
        "payout": 0.16,         # FY26 actual 16%
        "oa_pct": 1.00, "ol_pct": 0.85,
        "inv_growth": 0.05,
        "kd": 0.0836, "rf_spread_note": "company-guided WACD",
        "g": 0.05, "ronic": 0.115,
    },
}
