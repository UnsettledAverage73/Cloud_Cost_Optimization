"""
CloudPulse Dual-Currency Financial Engine
Provides high-precision currency conversion and localization for FinOps metrics.
Supports standard USD ($) and Indian Rupees (₹) with Lakhs (L) and Crores (Cr) notation.
"""

from typing import Tuple, Union, Optional

DEFAULT_USD_TO_INR_RATE = 84.00


class CurrencyConverter:
    """
    Financial currency converter and notation formatter.
    Supports standard US formatting and Indian numbering system (Lakhs and Crores).
    """

    def __init__(self, usd_to_inr_rate: float = DEFAULT_USD_TO_INR_RATE):
        self.usd_to_inr_rate = usd_to_inr_rate

    def to_inr(self, amount_usd: float) -> float:
        """Converts USD amount to INR."""
        return round(amount_usd * self.usd_to_inr_rate, 2)

    convert_usd_to_inr = to_inr

    def to_usd(self, amount_inr: float) -> float:
        """Converts INR amount to USD."""
        if self.usd_to_inr_rate == 0:
            return 0.0
        return round(amount_inr / self.usd_to_inr_rate, 2)

    convert_inr_to_usd = to_usd

    def format_inr(self, amount_inr: float, abbreviated: bool = True) -> str:
        """
        Formats INR into readable Indian currency notation:
        - >= 1 Crore (10,000,000): ₹X.XX Cr
        - >= 1 Lakh (100,000): ₹X.XX L
        - Below 1 Lakh: ₹X,XXX.XX with Indian comma grouping
        """
        if amount_inr is None:
            return "₹0.00"

        sign = "-" if amount_inr < 0 else ""
        abs_amount = abs(amount_inr)

        if abbreviated:
            if abs_amount >= 10_000_000:  # 1 Crore
                cr = abs_amount / 10_000_000
                return f"{sign}₹{cr:.2f} Cr"
            elif abs_amount >= 100_000:   # 1 Lakh
                lakh = abs_amount / 100_000
                return f"{sign}₹{lakh:.2f} L"

        # Indian comma grouping for standard numbers: e.g. 12,34,567.89
        int_part = int(abs_amount)
        decimal_part = f"{abs_amount - int_part:.2f}"[1:]  # .XX

        s = str(int_part)
        if len(s) <= 3:
            grouped = s
        else:
            last3 = s[-3:]
            remaining = s[:-3]
            chunks = []
            while remaining:
                chunks.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            grouped = ",".join(chunks) + "," + last3

        return f"{sign}₹{grouped}{decimal_part}"

    def format_usd(self, amount_usd: float, abbreviated: bool = True) -> str:
        """
        Formats USD amount:
        - >= $1,000,000: $X.XXM
        - >= $1,000: $X.XXK
        - Below $1,000: $X.XX
        """
        if amount_usd is None:
            return "$0.00"

        sign = "-" if amount_usd < 0 else ""
        abs_amount = abs(amount_usd)

        if abbreviated:
            if abs_amount >= 1_000_000:
                return f"{sign}${abs_amount / 1_000_000:.2f}M"
            elif abs_amount >= 100_000:
                return f"{sign}${abs_amount / 1_000:.1f}k"

        return f"{sign}${abs_amount:,.2f}"

    def format_dual(self, amount_usd: float, primary_currency: str = "USD") -> str:
        """
        Returns a formatted dual-currency string:
        e.g. '$68.40 (₹5,745.60)' or '₹5,745.60 ($68.40)'
        """
        inr_val = self.to_inr(amount_usd)
        usd_str = self.format_usd(amount_usd, abbreviated=False)
        inr_str = self.format_inr(inr_val, abbreviated=False)

        if primary_currency.upper() == "INR":
            inr_abbr = self.format_inr(inr_val, abbreviated=True)
            return f"{inr_abbr} ({usd_str})"
        return f"{usd_str} ({inr_str})"

    def convert_and_format(
        self,
        amount_usd: float,
        target_currency: str = "USD",
        abbreviated: bool = False
    ) -> str:
        """Direct single-currency formatter according to target_currency."""
        if target_currency.upper() == "INR":
            return self.format_inr(self.to_inr(amount_usd), abbreviated=abbreviated)
        return self.format_usd(amount_usd, abbreviated=abbreviated)


# Global singleton
currency_converter = CurrencyConverter()
currency_engine = currency_converter
