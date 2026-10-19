"""Explicit cost scenarios, separate from source-price forecasts."""
from __future__ import annotations

import math


def break_even(entry_ask=None, fee_rate=None, fixed_cost=None):
    """Fee is a fraction of exit gross; fixed_cost includes supplied other costs."""
    if any(value is None for value in (entry_ask, fee_rate, fixed_cost)):
        return {"status": "insufficient_data", "break_even_exit_price": None,
                "required": ["entry_ask", "fee_rate", "fixed_cost"]}
    if any(isinstance(value, bool) for value in (entry_ask, fee_rate, fixed_cost)):
        raise ValueError("Costs must be explicit finite numbers")
    ask, rate, fixed = map(float, (entry_ask, fee_rate, fixed_cost))
    if not all(math.isfinite(value) for value in (ask, rate, fixed)) or ask <= 0 or not 0 <= rate < 1 or fixed < 0:
        raise ValueError("Invalid explicit cost scenario")
    return {"status": "scenario_only", "entry_ask": ask, "fee_rate": rate,
            "fixed_cost": fixed, "break_even_exit_price": (ask + fixed) / (1 - rate),
            "execution_validated": False, "buy_sell_decision": None}
