"""Forecast and valuation inputs for the three covered companies (model v2).

EBITDA is built from two engines:
  core   NTPC: regulated EBITDA scales with regulated equity (CERC cost-plus: equity is 30% of
         commissioned regulated capital and earns a 15.5% post-tax RoE; debt, depreciation and
         O&M recoveries scale with the same asset base).
         Tata Power / JSW: existing EBITDA grows at a drift, and non-RE assets commissioned
         earn an EBITDA yield calibrated on FY19-26 history.
  RE     operating MW x capacity utilisation (CUF) x 8,760 h x tariff x EBITDA margin, with MW
         added = RE share of assets commissioned / cost per MW.
Capex starts from management guidance (see data/processed/guidance_sentences.csv), haircut
for execution. Revenue follows from each engine's own margin, so no margin path is assumed.
Years run FY27E..FY36E.
"""

MARKET = {
    # India 10Y G-sec close 14-Aug-2026 (Investing.com historical data); Damodaran Jan-2026 India default
    # spread 1.87% and total ERP 7.08%. Stripping the default spread from the G-sec avoids
    # counting country risk twice.
    "gsec_10y": 0.06762,
    "default_spread": 0.0187,
    "erp": 0.0708,
    "tax": 0.25,
    "valuation_date": "2026-08-14",
    "stub": 229 / 365,     # fraction of FY27 remaining after the valuation date (14-Aug-26 to 31-Mar-27)
    "dcf_weight": 0.5,     # Tata Power / JSW: 12-month target = 50% DCF + 50% FY27E EV/EBITDA
    "min_cash": 0.0,       # incremental cash floor; shortfalls are drawn on a revolver
    "holdco_discount": 0.20,
}

COMPANIES = {
    "NTPC": {
        "rationale": {
            "capex": "Q1FY27 call: group capex Rs 1,08,000 cr for FY27, Rs 5,97,000 cr over FY28-32 "
                     "(Rs 1,19,400 cr/yr) and Rs 9,63,000 cr over FY33-37, mostly nuclear. FY26 actual "
                     "was Rs 49,068 cr, so the step-up is haircut to 70%. FY33-36 is held at the "
                     "FY28-32 run-rate because long-gestation nuclear capex adds little EBITDA in the horizon.",
            "regulated": "Consolidated regulated equity Rs 1,20,319 cr at Mar-26 vs Rs 1,08,791 cr a year "
                         "earlier (Q4FY26 call); regulated RoE 15.5% post-tax (CMD, Q1FY27).",
            "renewables": "Group RE 11,578 MW at Mar-26 (12,068 MW incl. 490 MW added in FY27, Q4FY26 call); "
                          "NGEL generated 14.6 BU in FY26 (implied CUF ~18.5%) on TTM revenue of Rs 3,285 cr "
                          "(~Rs 2.25/kWh). NGEL capex Rs 35,800 cr for ~8 GW (Rs 4.5 cr/MW); about half of "
                          "group capex goes to RE (Q4FY26 call). At guided capex the model commissions ~7 GW "
                          "of RE in FY27 vs 7-8 GW guided.",
            "valuation": "Sum of the parts at Mar-27: regulated equity by residual income (FY27E book plus the "
                         "present value of (RoE - Ke) x opening book along the model's regulated-equity path to "
                         "FY36, then growth of 5%), equity in regulated CWIP at book, and the 89.01% stake in listed "
                         "NTPC Green at market less a 20% holding-company discount. JVs are not added separately: "
                         "consolidated regulated equity already includes them. DCF and EV/EBITDA are cross-checks.",
        },
        "regulated": True,
        "regeq_prev": 108791, "regeq0": 120319, "reg_equity_share": 0.30,
        "roe": 0.159, "pb_growth": 0.05,   # 15.5% normative + ~0.4pp net operational gains (9MFY26: Rs 832 cr
                                           # gains vs Rs 454 cr under-recoveries, annualised, on Rs 1.15 lakh cr)
        "jv_profit0": 2864, "jv_growth": 0.05,   # share of JV profit FY26 (Q4FY26 call), post-tax, retained
        "re_mw_prev": 6840, "re_mw0": 11578,
        "ngel_stake": 0.8901,
        "re_share": 0.50, "re_cost": 4.5, "re_cuf": 0.185, "re_tariff": 2.30, "re_margin": 0.85,
        "capex_guided": [108000, 119400, 119400, 119400, 119400, 119400, 119400, 119400, 119400, 119400],
        "execution": 0.70,
        "other_income_pct": 0.025,
        "dep_rate": 0.070,        # depreciation / opening net block
        "capitalisation": 0.40,   # share of (opening CWIP + capex) commissioned in the year
        "debt_share": 0.50,       # share of capex funded by new term debt
        "int_rate": 0.055,        # interest / average debt (net of capitalised interest)
        "payout": 0.32,           # FY26 actual 32% (Screener)
        "oa_pct": 0.70, "ol_pct": 0.41,   # non-cash other assets / liabilities (ex minorities) % sales
        "inv_growth": 0.05,
        "kd": 0.074, "rf_spread_note": "AAA PSU",
        "g": 0.05, "ronic": 0.12,
    },
    "TATAPOWER": {
        "rationale": {
            "capex": "Q1FY27 call: Rs 25,000 cr lined up for FY27, half RE and the rest FGD and T&D, with a "
                     "'similar kind of capital outlay' after. FY26 spend of ~Rs 15,600 cr vs ~Rs 22,000 cr "
                     "guided implies ~70-75% delivery; 75% assumed.",
            "core": "Existing EBITDA drifts 4% a year: Mumbai transmission (~Rs 1,000 cr capex a year), "
                    "distribution and rooftop/EPC. Non-RE assets commissioned earn 12% (FY19-26: 12.2%).",
            "renewables": "Rs 6 cr/MW for hybrid/FDRE-heavy additions (Rs 12-15k cr for ~2 GW a year, "
                          "Q4FY26 call), CUF 27%, Rs 3.2/kWh, 88% EBITDA margin. Model adds ~1.4 GW in FY27.",
            "valuation": "12-month target: 50% DCF rolled forward at Ke, 50% peer EV/EBITDA on FY27E.",
        },
        "regulated": False, "jv_profit0": 0, "jv_growth": 0.0,
        "base_drift": 0.04, "asset_yield": 0.12,
        "re_mw_prev": 0, "re_mw0": None,          # None: FY26 new MW = RE share of FY26 commissioning
        "re_share": 0.50, "re_cost": 6.0, "re_cuf": 0.27, "re_tariff": 3.20, "re_margin": 0.88,
        "capex_guided": [25000] * 10,
        "execution": 0.75,
        "other_income_pct": 0.05,
        "dep_rate": 0.061,
        "capitalisation": 0.50,
        "debt_share": 0.60,
        "int_rate": 0.076,
        "payout": 0.21,
        "oa_pct": 0.90, "ol_pct": 0.81,
        "inv_growth": 0.05,
        "kd": 0.080, "rf_spread_note": "AA+ private",
        "g": 0.05, "ronic": 0.11,
    },
    "JSWENERGY": {
        "rationale": {
            "capex": "Q4FY26 and Q1FY27 calls: ~Rs 20,000 cr capex and 3 GW additions in FY27 (1.1 GW done "
                     "by July), Rs 4-5k cr of it thermal and pumped storage; 30 GW generation target by FY30 "
                     "with 32.1 GW locked in. Rs 22,000 cr a year to FY30, Rs 15,000 cr after; 90% execution.",
            "core": "Existing 13.45 GW fleet drifts 1% a year; the 25-yr Utkal PPA at Rs 5.78/unit anchors "
                    "thermal. Non-RE assets commissioned (Mahanadi expansion, pumped hydro) earn 15%.",
            "renewables": "Rs 5.2 cr/MW (RE share of Rs 20,000 cr over 3 GW), CUF 28% with ~35-40% wind, "
                          "Rs 3.1/kWh, 90% margin. Model adds ~2.9 GW in FY27 vs 3 GW guided.",
            "valuation": "12-month target: 50% DCF rolled forward at Ke, 50% peer EV/EBITDA on FY27E.",
        },
        "regulated": False, "jv_profit0": 0, "jv_growth": 0.0,
        "base_drift": 0.01, "asset_yield": 0.15,
        "re_mw_prev": 0, "re_mw0": None,
        "re_share": 0.78, "re_cost": 5.2, "re_cuf": 0.28, "re_tariff": 3.10, "re_margin": 0.90,
        "capex_guided": [20000, 22000, 22000, 22000, 15000, 15000, 15000, 15000, 15000, 15000],
        "execution": 0.90,
        "other_income_pct": 0.05,
        "dep_rate": 0.060,
        "capitalisation": 0.55,
        "debt_share": 0.65,
        "int_rate": 0.084,
        "payout": 0.16,
        "oa_pct": 1.00, "ol_pct": 0.70,
        "inv_growth": 0.05,
        "kd": 0.0836, "rf_spread_note": "company-guided WACD",
        "g": 0.05, "ronic": 0.115,
    },
}
