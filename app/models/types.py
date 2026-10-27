from decimal import Decimal

from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator

_CENT = Decimal("0.01")


class Money(TypeDecorator):
    """Decimal in Python, whole cents in the database.

    SQLite has no exact decimal type (it would silently store a float), so
    we store the amount as an integer number of cents and convert back to
    Decimal when reading. No rounding errors can occur.
    """

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        cents = Decimal(value).scaleb(2)
        if cents != cents.to_integral_value():
            raise ValueError("Money supports at most 2 decimal places")
        return int(cents)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return (Decimal(value).scaleb(-2)).quantize(_CENT)
