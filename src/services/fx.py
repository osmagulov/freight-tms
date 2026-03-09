# Static FX rates — updated manually when rates need changing.
# Rate = how many KZT per 1 unit of the foreign currency.
# Last updated: 2026-03-09 (update this comment when rates are changed)
FX_RATES_TO_KZT: dict[str, float] = {
    "KZT": 1.0,
    "RUB": 5.5,    # ~1 RUB = 5.5 KZT (approximate)
    "USD": 450.0,  # ~1 USD = 450 KZT (approximate)
    "EUR": 490.0,  # ~1 EUR = 490 KZT (approximate)
}

def get_fx_rate(currency: str) -> float:
    """Return KZT conversion rate for currency. Raises KeyError if currency not in table."""
    return FX_RATES_TO_KZT[currency.upper()]
