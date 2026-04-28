"""
[DEV] Atlas-MH Rater — Premium Engine
Multiplicative factor model:
  Base × Territory × Tier × [Variables] = Final Premium
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


class PremiumEngine:
    """
    Core premium calculation engine.
    Applies: Base Rate × Territory Factor × Tier Factor × Variable Factors
    """

    def __init__(self, carrier_code: str):
        self.carrier_code = carrier_code

    def calculate(
        self,
        base_rate: float,
        territory_factor: float,
        tier_factor: float,
        variable_factors: Optional[dict[str, float]] = None,
    ) -> float:
        """
        Calculate final premium using multiplicative factor model.
        Returns premium rounded to 2 decimal places.
        """
        premium = Decimal(str(base_rate)) \
            * Decimal(str(territory_factor)) \
            * Decimal(str(tier_factor))

        if variable_factors:
            for factor in variable_factors.values():
                premium *= Decimal(str(factor))

        return float(premium.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))