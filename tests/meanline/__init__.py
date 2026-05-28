"""Mean-line validation test suite.

Cases mapped to SPEC_SHEET.md §12:
- RIT-1: Whitney & Stewart 1974, NASA TN D-7508 — `test_rit1_whitney_stewart.py`
- RIT-2: Glassman 1973, NASA SP-290 Vol 3 — `test_rit2_glassman.py`
- CC-1: Eckardt 1976, Rotor A — `test_cc1_eckardt_rotor_a.py`
- CC-2: Eckardt 1980, Rotor O — `test_cc2_eckardt_rotor_o.py`

Plus framework tests:
- `test_slip_factor_limits.py` — closes SR-006 (Z → ∞ limit)
- `test_regime_refuse.py` — SPEC_SHEET §13 (M_rel > 2.5)
"""
