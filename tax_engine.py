"""
Deterministic tax calculation engine.

No AI is used here — this module applies the official 2026 single-filer
federal tax brackets and standard deduction using plain arithmetic so the
result is reproducible and auditable.
"""

from typing import Dict


# 2026 single-filer standard deduction
STANDARD_DEDUCTION_2026 = 15300

# 2026 single-filer progressive tax brackets: (upper_bound, rate)
# Income above the last bracket's lower bound is taxed at the final rate.
# upper_bound of None marks the top (unbounded) bracket.
TAX_BRACKETS_2026_SINGLE = [
    (11925, 0.10),
    (48475, 0.12),
    (103350, 0.22),
    (197300, 0.24),
    (250525, 0.32),
    (626350, 0.35),
    (None, 0.37),
]


def _bracket_breakdown(taxable_income: float) -> list:
    """
    Split taxable_income across the progressive bracket schedule and return
    a per-bracket breakdown (only brackets that actually applied), so the UI
    can show exactly how the total tax liability was derived.
    """
    breakdown = []
    if taxable_income <= 0:
        return breakdown

    lower_bound = 0
    for upper_bound, rate in TAX_BRACKETS_2026_SINGLE:
        if upper_bound is None or taxable_income <= upper_bound:
            amount_in_bracket = taxable_income - lower_bound
            final_bracket = True
        else:
            amount_in_bracket = upper_bound - lower_bound
            final_bracket = False

        if amount_in_bracket > 0:
            breakdown.append(
                {
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                    "rate": rate,
                    "amount_in_bracket": round(amount_in_bracket, 2),
                    "tax_for_bracket": round(amount_in_bracket * rate, 2),
                }
            )

        if final_bracket:
            break
        lower_bound = upper_bound

    return breakdown


def _progressive_tax(taxable_income: float) -> float:
    """Apply the progressive bracket schedule to a taxable income amount."""
    return sum(b["tax_for_bracket"] for b in _bracket_breakdown(taxable_income))


def calculate_us_tax(gross_income: float, deduction_dict: Dict[str, float]) -> dict:
    """
    Calculate estimated 2026 US federal tax liability for a single filer.

    Args:
        gross_income: Total gross income reported by the user.
        deduction_dict: Mapping of deduction category -> dollar amount
            (e.g. {"student_loan_interest": 2000, "charitable_giving": 500}).

    Returns:
        A dictionary with the full breakdown of the calculation, including
        whichever deduction (standard or itemized) was applied, the taxable
        income, the computed tax, and the estimated refund or amount owed.
    """
    gross_income = max(0.0, float(gross_income or 0))

    itemized_total = sum(float(v) for v in (deduction_dict or {}).values() if v)

    # Always take whichever deduction saves the user more money.
    used_standard_deduction = itemized_total <= STANDARD_DEDUCTION_2026
    applied_deduction = max(STANDARD_DEDUCTION_2026, itemized_total)

    taxable_income = max(0.0, gross_income - applied_deduction)
    bracket_breakdown = _bracket_breakdown(taxable_income)
    tax_liability = round(sum(b["tax_for_bracket"] for b in bracket_breakdown), 2)

    # Assume federal withholding at a flat 15% of gross income as a simple
    # proxy for "taxes already paid" so the app can show a refund/owed figure.
    estimated_withholding = round(gross_income * 0.15, 2)
    refund_or_owed = round(estimated_withholding - tax_liability, 2)

    return {
        "gross_income": round(gross_income, 2),
        "standard_deduction": STANDARD_DEDUCTION_2026,
        "itemized_deduction_total": round(itemized_total, 2),
        "deduction_used": round(applied_deduction, 2),
        "used_standard_deduction": used_standard_deduction,
        "taxable_income": round(taxable_income, 2),
        "tax_liability": tax_liability,
        "bracket_breakdown": bracket_breakdown,
        "estimated_withholding": estimated_withholding,
        "refund_or_owed": refund_or_owed,
        "is_refund": refund_or_owed >= 0,
    }
