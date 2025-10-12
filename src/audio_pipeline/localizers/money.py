"""Money-related data structures shared by localized narrators."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

__all__ = ["MoneyAmount"]


@dataclass(frozen=True)
class MoneyAmount:
    """Structured financial value expressed in rupees."""

    rupees: Decimal
    magnitude: Decimal
    unit_key: Optional[str]
    raw_text: str
