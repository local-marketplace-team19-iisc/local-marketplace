from enum import Enum


class UnitType(str, Enum):
    """Standardized grocery unit set for catalog products (spec FR-7).

    Covers volume, weight, and count units.
    """

    LITER = "LITER"
    MILLILITER = "MILLILITER"
    KILOGRAM = "KILOGRAM"
    GRAM = "GRAM"
    PIECE = "PIECE"
    PACK = "PACK"
    DOZEN = "DOZEN"
