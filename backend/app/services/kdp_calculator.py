from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

ACOS_RATIO = Decimal("1.5")

HARDCOVER_COSTS = {
    "black": {
        "75-108": {
            "regular": {
                "US": {"fixed": Decimal("5.65"), "per_page": Decimal("0"), "currency": "USD"},
                "UK": {"fixed": Decimal("4.15"), "per_page": Decimal("0"), "currency": "GBP"},
                "GB": {"fixed": Decimal("4.15"), "per_page": Decimal("0"), "currency": "GBP"},
                "DE": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "FR": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "ES": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "IT": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "NL": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "IE": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "BE": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "PL": {"fixed": Decimal("20.34"), "per_page": Decimal("0"), "currency": "PLN"},
                "SE": {"fixed": Decimal("48.49"), "per_page": Decimal("0"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("5.65"), "per_page": Decimal("0"), "currency": "USD"},
                "UK": {"fixed": Decimal("4.15"), "per_page": Decimal("0"), "currency": "GBP"},
                "GB": {"fixed": Decimal("4.15"), "per_page": Decimal("0"), "currency": "GBP"},
                "DE": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "FR": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "ES": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "IT": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "NL": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "IE": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "BE": {"fixed": Decimal("4.65"), "per_page": Decimal("0"), "currency": "EUR"},
                "PL": {"fixed": Decimal("20.34"), "per_page": Decimal("0"), "currency": "PLN"},
                "SE": {"fixed": Decimal("48.49"), "per_page": Decimal("0"), "currency": "SEK"},
            },
        },
        "110-550": {
            "regular": {
                "US": {"fixed": Decimal("5.65"), "per_page": Decimal("0.012"), "currency": "USD"},
                "UK": {"fixed": Decimal("4.15"), "per_page": Decimal("0.010"), "currency": "GBP"},
                "GB": {"fixed": Decimal("4.15"), "per_page": Decimal("0.010"), "currency": "GBP"},
                "DE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "FR": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "ES": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "IT": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "NL": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "IE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "BE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "PL": {"fixed": Decimal("20.34"), "per_page": Decimal("0.056"), "currency": "PLN"},
                "SE": {"fixed": Decimal("48.49"), "per_page": Decimal("0.134"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("5.65"), "per_page": Decimal("0.017"), "currency": "USD"},
                "UK": {"fixed": Decimal("4.15"), "per_page": Decimal("0.012"), "currency": "GBP"},
                "GB": {"fixed": Decimal("4.15"), "per_page": Decimal("0.012"), "currency": "GBP"},
                "DE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "FR": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "ES": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "IT": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "NL": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "IE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "BE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "PL": {"fixed": Decimal("20.34"), "per_page": Decimal("0.075"), "currency": "PLN"},
                "SE": {"fixed": Decimal("48.49"), "per_page": Decimal("0.179"), "currency": "SEK"},
            },
        },
    },
    "color": {
        "75-550": {
            "regular": {
                "US": {"fixed": Decimal("5.65"), "per_page": Decimal("0.065"), "currency": "USD"},
                "UK": {"fixed": Decimal("4.15"), "per_page": Decimal("0.045"), "currency": "GBP"},
                "GB": {"fixed": Decimal("4.15"), "per_page": Decimal("0.045"), "currency": "GBP"},
                "DE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "FR": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "ES": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "IT": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "NL": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "IE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "BE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.057"), "currency": "EUR"},
                "PL": {"fixed": Decimal("21.78"), "per_page": Decimal("0.267"), "currency": "PLN"},
                "SE": {"fixed": Decimal("51.91"), "per_page": Decimal("0.636"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("5.65"), "per_page": Decimal("0.080"), "currency": "USD"},
                "UK": {"fixed": Decimal("4.15"), "per_page": Decimal("0.060"), "currency": "GBP"},
                "GB": {"fixed": Decimal("4.15"), "per_page": Decimal("0.060"), "currency": "GBP"},
                "DE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "FR": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "ES": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "IT": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "NL": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "IE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "BE": {"fixed": Decimal("4.65"), "per_page": Decimal("0.072"), "currency": "EUR"},
                "PL": {"fixed": Decimal("21.78"), "per_page": Decimal("0.337"), "currency": "PLN"},
                "SE": {"fixed": Decimal("51.91"), "per_page": Decimal("0.804"), "currency": "SEK"},
            },
        },
    },
}

KDP_COSTS = {
    "black": {
        "24-108": {
            "regular": {
                "US": {"fixed": Decimal("2.30"), "per_page": Decimal("0"), "currency": "USD"},
                "CA": {"fixed": Decimal("2.99"), "per_page": Decimal("0"), "currency": "CAD"},
                "UK": {"fixed": Decimal("1.93"), "per_page": Decimal("0"), "currency": "GBP"},
                "GB": {"fixed": Decimal("1.93"), "per_page": Decimal("0"), "currency": "GBP"},
                "DE": {"fixed": Decimal("2.05"), "per_page": Decimal("0"), "currency": "EUR"},
                "FR": {"fixed": Decimal("2.05"), "per_page": Decimal("0"), "currency": "EUR"},
                "ES": {"fixed": Decimal("2.05"), "per_page": Decimal("0"), "currency": "EUR"},
                "IT": {"fixed": Decimal("2.05"), "per_page": Decimal("0"), "currency": "EUR"},
                "NL": {"fixed": Decimal("2.05"), "per_page": Decimal("0"), "currency": "EUR"},
                "JP": {"fixed": Decimal("422"), "per_page": Decimal("0"), "currency": "JPY"},
                "AU": {"fixed": Decimal("4.74"), "per_page": Decimal("0"), "currency": "AUD"},
                "PL": {"fixed": Decimal("9.58"), "per_page": Decimal("0"), "currency": "PLN"},
                "SE": {"fixed": Decimal("22.84"), "per_page": Decimal("0"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("2.84"), "per_page": Decimal("0"), "currency": "USD"},
                "CA": {"fixed": Decimal("3.53"), "per_page": Decimal("0"), "currency": "CAD"},
                "UK": {"fixed": Decimal("2.15"), "per_page": Decimal("0"), "currency": "GBP"},
                "GB": {"fixed": Decimal("2.15"), "per_page": Decimal("0"), "currency": "GBP"},
                "DE": {"fixed": Decimal("2.48"), "per_page": Decimal("0"), "currency": "EUR"},
                "FR": {"fixed": Decimal("2.48"), "per_page": Decimal("0"), "currency": "EUR"},
                "ES": {"fixed": Decimal("2.48"), "per_page": Decimal("0"), "currency": "EUR"},
                "IT": {"fixed": Decimal("2.48"), "per_page": Decimal("0"), "currency": "EUR"},
                "NL": {"fixed": Decimal("2.48"), "per_page": Decimal("0"), "currency": "EUR"},
                "JP": {"fixed": Decimal("530"), "per_page": Decimal("0"), "currency": "JPY"},
                "AU": {"fixed": Decimal("5.28"), "per_page": Decimal("0"), "currency": "AUD"},
                "PL": {"fixed": Decimal("11.61"), "per_page": Decimal("0"), "currency": "PLN"},
                "SE": {"fixed": Decimal("27.67"), "per_page": Decimal("0"), "currency": "SEK"},
            },
        },
        "110-828": {
            "regular": {
                "US": {"fixed": Decimal("1.00"), "per_page": Decimal("0.012"), "currency": "USD"},
                "CA": {"fixed": Decimal("1.26"), "per_page": Decimal("0.016"), "currency": "CAD"},
                "UK": {"fixed": Decimal("0.85"), "per_page": Decimal("0.010"), "currency": "GBP"},
                "GB": {"fixed": Decimal("0.85"), "per_page": Decimal("0.010"), "currency": "GBP"},
                "DE": {"fixed": Decimal("0.75"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "FR": {"fixed": Decimal("0.75"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "ES": {"fixed": Decimal("0.75"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "IT": {"fixed": Decimal("0.75"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "NL": {"fixed": Decimal("0.75"), "per_page": Decimal("0.012"), "currency": "EUR"},
                "JP": {"fixed": Decimal("206"), "per_page": Decimal("2"), "currency": "JPY"},
                "AU": {"fixed": Decimal("2.42"), "per_page": Decimal("0.022"), "currency": "AUD"},
                "PL": {"fixed": Decimal("3.51"), "per_page": Decimal("0.056"), "currency": "PLN"},
                "SE": {"fixed": Decimal("8.37"), "per_page": Decimal("0.134"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("1.00"), "per_page": Decimal("0.017"), "currency": "USD"},
                "CA": {"fixed": Decimal("1.26"), "per_page": Decimal("0.021"), "currency": "CAD"},
                "UK": {"fixed": Decimal("0.85"), "per_page": Decimal("0.012"), "currency": "GBP"},
                "GB": {"fixed": Decimal("0.85"), "per_page": Decimal("0.012"), "currency": "GBP"},
                "DE": {"fixed": Decimal("0.75"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "FR": {"fixed": Decimal("0.75"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "ES": {"fixed": Decimal("0.75"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "IT": {"fixed": Decimal("0.75"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "NL": {"fixed": Decimal("0.75"), "per_page": Decimal("0.016"), "currency": "EUR"},
                "JP": {"fixed": Decimal("206"), "per_page": Decimal("3"), "currency": "JPY"},
                "AU": {"fixed": Decimal("2.42"), "per_page": Decimal("0.027"), "currency": "AUD"},
                "PL": {"fixed": Decimal("3.51"), "per_page": Decimal("0.075"), "currency": "PLN"},
                "SE": {"fixed": Decimal("8.37"), "per_page": Decimal("0.179"), "currency": "SEK"},
            },
        },
    },
    "premium_color": {
        "24-40": {
            "regular": {
                "US": {"fixed": Decimal("3.60"), "per_page": Decimal("0"), "currency": "USD"},
                "CA": {"fixed": Decimal("4.66"), "per_page": Decimal("0"), "currency": "CAD"},
                "UK": {"fixed": Decimal("2.59"), "per_page": Decimal("0"), "currency": "GBP"},
                "GB": {"fixed": Decimal("2.59"), "per_page": Decimal("0"), "currency": "GBP"},
                "DE": {"fixed": Decimal("2.85"), "per_page": Decimal("0"), "currency": "EUR"},
                "FR": {"fixed": Decimal("2.85"), "per_page": Decimal("0"), "currency": "EUR"},
                "ES": {"fixed": Decimal("2.85"), "per_page": Decimal("0"), "currency": "EUR"},
                "IT": {"fixed": Decimal("2.85"), "per_page": Decimal("0"), "currency": "EUR"},
                "NL": {"fixed": Decimal("2.85"), "per_page": Decimal("0"), "currency": "EUR"},
                "JP": {"fixed": Decimal("475"), "per_page": Decimal("0"), "currency": "JPY"},
                "AU": {"fixed": Decimal("5.82"), "per_page": Decimal("0"), "currency": "AUD"},
                "PL": {"fixed": Decimal("12.86"), "per_page": Decimal("0"), "currency": "PLN"},
                "SE": {"fixed": Decimal("30.65"), "per_page": Decimal("0"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("4.20"), "per_page": Decimal("0"), "currency": "USD"},
                "CA": {"fixed": Decimal("5.26"), "per_page": Decimal("0"), "currency": "CAD"},
                "UK": {"fixed": Decimal("3.24"), "per_page": Decimal("0"), "currency": "GBP"},
                "GB": {"fixed": Decimal("3.24"), "per_page": Decimal("0"), "currency": "GBP"},
                "DE": {"fixed": Decimal("3.61"), "per_page": Decimal("0"), "currency": "EUR"},
                "FR": {"fixed": Decimal("3.61"), "per_page": Decimal("0"), "currency": "EUR"},
                "ES": {"fixed": Decimal("3.61"), "per_page": Decimal("0"), "currency": "EUR"},
                "IT": {"fixed": Decimal("3.61"), "per_page": Decimal("0"), "currency": "EUR"},
                "NL": {"fixed": Decimal("3.61"), "per_page": Decimal("0"), "currency": "EUR"},
                "JP": {"fixed": Decimal("475"), "per_page": Decimal("0"), "currency": "JPY"},
                "AU": {"fixed": Decimal("6.42"), "per_page": Decimal("0"), "currency": "AUD"},
                "PL": {"fixed": Decimal("15.32"), "per_page": Decimal("0"), "currency": "PLN"},
                "SE": {"fixed": Decimal("36.51"), "per_page": Decimal("0"), "currency": "SEK"},
            },
        },
        "42-828": {
            "regular": {
                "US": {"fixed": Decimal("1.00"), "per_page": Decimal("0.065"), "currency": "USD"},
                "CA": {"fixed": Decimal("1.26"), "per_page": Decimal("0.085"), "currency": "CAD"},
                "UK": {"fixed": Decimal("0.85"), "per_page": Decimal("0.0435"), "currency": "GBP"},
                "GB": {"fixed": Decimal("0.85"), "per_page": Decimal("0.0435"), "currency": "GBP"},
                "DE": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0525"), "currency": "EUR"},
                "FR": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0525"), "currency": "EUR"},
                "ES": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0525"), "currency": "EUR"},
                "IT": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0525"), "currency": "EUR"},
                "NL": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0525"), "currency": "EUR"},
                "JP": {"fixed": Decimal("206"), "per_page": Decimal("4"), "currency": "JPY"},
                "AU": {"fixed": Decimal("2.42"), "per_page": Decimal("0.085"), "currency": "AUD"},
                "PL": {"fixed": Decimal("3.51"), "per_page": Decimal("0.267"), "currency": "PLN"},
                "SE": {"fixed": Decimal("8.37"), "per_page": Decimal("0.636"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("1.00"), "per_page": Decimal("0.08"), "currency": "USD"},
                "CA": {"fixed": Decimal("1.26"), "per_page": Decimal("0.10"), "currency": "CAD"},
                "UK": {"fixed": Decimal("0.85"), "per_page": Decimal("0.0598"), "currency": "GBP"},
                "GB": {"fixed": Decimal("0.85"), "per_page": Decimal("0.0598"), "currency": "GBP"},
                "DE": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0715"), "currency": "EUR"},
                "FR": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0715"), "currency": "EUR"},
                "ES": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0715"), "currency": "EUR"},
                "IT": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0715"), "currency": "EUR"},
                "NL": {"fixed": Decimal("0.75"), "per_page": Decimal("0.0715"), "currency": "EUR"},
                "JP": {"fixed": Decimal("206"), "per_page": Decimal("5"), "currency": "JPY"},
                "AU": {"fixed": Decimal("2.42"), "per_page": Decimal("0.100"), "currency": "AUD"},
                "PL": {"fixed": Decimal("3.51"), "per_page": Decimal("0.337"), "currency": "PLN"},
                "SE": {"fixed": Decimal("8.37"), "per_page": Decimal("0.804"), "currency": "SEK"},
            },
        },
    },
    "standard_color": {
        "72-600": {
            "regular": {
                "US": {"fixed": Decimal("1.00"), "per_page": Decimal("0.0255"), "currency": "USD"},
                "CA": {"fixed": Decimal("1.26"), "per_page": Decimal("0.037"), "currency": "CAD"},
                "UK": {"fixed": Decimal("0.85"), "per_page": Decimal("0.020"), "currency": "GBP"},
                "GB": {"fixed": Decimal("0.85"), "per_page": Decimal("0.020"), "currency": "GBP"},
                "DE": {"fixed": Decimal("0.75"), "per_page": Decimal("0.024"), "currency": "EUR"},
                "FR": {"fixed": Decimal("0.75"), "per_page": Decimal("0.024"), "currency": "EUR"},
                "ES": {"fixed": Decimal("0.75"), "per_page": Decimal("0.024"), "currency": "EUR"},
                "IT": {"fixed": Decimal("0.75"), "per_page": Decimal("0.024"), "currency": "EUR"},
                "NL": {"fixed": Decimal("0.75"), "per_page": Decimal("0.024"), "currency": "EUR"},
                "PL": {"fixed": Decimal("3.51"), "per_page": Decimal("0.112"), "currency": "PLN"},
                "SE": {"fixed": Decimal("8.37"), "per_page": Decimal("0.268"), "currency": "SEK"},
            },
            "large": {
                "US": {"fixed": Decimal("1.00"), "per_page": Decimal("0.0402"), "currency": "USD"},
                "CA": {"fixed": Decimal("1.26"), "per_page": Decimal("0.052"), "currency": "CAD"},
                "UK": {"fixed": Decimal("0.85"), "per_page": Decimal("0.027"), "currency": "GBP"},
                "GB": {"fixed": Decimal("0.85"), "per_page": Decimal("0.027"), "currency": "GBP"},
                "DE": {"fixed": Decimal("0.75"), "per_page": Decimal("0.035"), "currency": "EUR"},
                "FR": {"fixed": Decimal("0.75"), "per_page": Decimal("0.035"), "currency": "EUR"},
                "ES": {"fixed": Decimal("0.75"), "per_page": Decimal("0.035"), "currency": "EUR"},
                "IT": {"fixed": Decimal("0.75"), "per_page": Decimal("0.035"), "currency": "EUR"},
                "NL": {"fixed": Decimal("0.75"), "per_page": Decimal("0.035"), "currency": "EUR"},
                "PL": {"fixed": Decimal("3.51"), "per_page": Decimal("0.164"), "currency": "PLN"},
                "SE": {"fixed": Decimal("8.37"), "per_page": Decimal("0.3691"), "currency": "SEK"},
            },
        },
    },
}


def get_trim_category(width_inches: Optional[float], height_inches: Optional[float]) -> str:
    if width_inches is None or height_inches is None:
        return "regular"
    if width_inches > 6.12 or height_inches > 9.0:
        return "large"
    return "regular"


def get_page_range(ink_type: str, pages: int) -> Optional[str]:
    if ink_type == "black":
        if 24 <= pages <= 108:
            return "24-108"
        elif 110 <= pages <= 828:
            return "110-828"
    elif ink_type == "premium_color":
        if 24 <= pages <= 40:
            return "24-40"
        elif 42 <= pages <= 828:
            return "42-828"
    elif ink_type == "standard_color":
        if 72 <= pages <= 600:
            return "72-600"
    return None


def get_hardcover_page_range(ink_type: str, pages: int) -> Optional[str]:
    if ink_type == "black":
        if 75 <= pages <= 108:
            return "75-108"
        elif 110 <= pages <= 550:
            return "110-550"
    elif ink_type in ("color", "premium_color", "standard_color"):
        if 75 <= pages <= 550:
            return "75-550"
    return None


def calculate_hardcover_printing_cost(
    pages: int,
    marketplace: str,
    ink_type: str = "black",
    width_inches: Optional[float] = None,
    height_inches: Optional[float] = None,
) -> Optional[Tuple[Decimal, str]]:
    marketplace = marketplace.upper()
    if marketplace == "UK":
        marketplace = "GB"
    
    hc_ink = "color" if ink_type in ("color", "premium_color", "standard_color") else "black"
    
    trim_category = get_trim_category(width_inches, height_inches)
    page_range = get_hardcover_page_range(ink_type, pages)
    
    if page_range is None:
        return None
    
    ink_costs = HARDCOVER_COSTS.get(hc_ink)
    if not ink_costs:
        return None
    
    range_costs = ink_costs.get(page_range)
    if not range_costs:
        return None
    
    trim_costs = range_costs.get(trim_category)
    if not trim_costs:
        return None
    
    market_costs = trim_costs.get(marketplace)
    if not market_costs:
        market_costs = trim_costs.get("US")
        if not market_costs:
            return None
    
    fixed_cost = market_costs["fixed"]
    per_page_cost = market_costs["per_page"]
    currency = market_costs["currency"]
    
    c_print = fixed_cost + (Decimal(pages) * per_page_cost)
    c_print = c_print.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return c_print, currency


ROYALTY_THRESHOLDS = {
    "USD": Decimal("0"),
    "EUR": Decimal("0"),
    "GBP": Decimal("0"),
    "CAD": Decimal("0"),
    "AUD": Decimal("0"),
    "JPY": Decimal("0"),
    "PLN": Decimal("0"),
    "SEK": Decimal("0"),
}


def get_royalty_rate(price: float, is_hardcover: bool = False) -> float:
    return 0.60


def calculate_printing_cost(
    pages: int,
    marketplace: str,
    ink_type: str = "black",
    width_inches: Optional[float] = None,
    height_inches: Optional[float] = None,
) -> Optional[Tuple[Decimal, str]]:
    marketplace = marketplace.upper()
    if marketplace == "UK":
        marketplace = "GB"
    
    trim_category = get_trim_category(width_inches, height_inches)
    page_range = get_page_range(ink_type, pages)
    
    if page_range is None:
        return None
    
    ink_costs = KDP_COSTS.get(ink_type)
    if not ink_costs:
        return None
    
    range_costs = ink_costs.get(page_range)
    if not range_costs:
        return None
    
    trim_costs = range_costs.get(trim_category)
    if not trim_costs:
        return None
    
    market_costs = trim_costs.get(marketplace)
    if not market_costs:
        market_costs = trim_costs.get("US")
        if not market_costs:
            return None
    
    fixed_cost = market_costs["fixed"]
    per_page_cost = market_costs["per_page"]
    currency = market_costs["currency"]
    
    c_print = fixed_cost + (Decimal(pages) * per_page_cost)
    c_print = c_print.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return c_print, currency


def calculate_acos_values(
    price: float,
    c_print: float,
    royalty_rate: float = 0.6,
    k: float = 1.5,
) -> Tuple[float, float, float]:
    price_d = Decimal(str(price))
    c_print_d = Decimal(str(c_print))
    r = Decimal(str(royalty_rate))
    k_d = Decimal(str(k))
    
    r_net = (price_d * r) - c_print_d
    
    if price_d > 0:
        acos_be = (r_net / price_d) * Decimal("100")
    else:
        acos_be = Decimal("0")
    
    if k_d > 0:
        acos_opt = acos_be / k_d
    else:
        acos_opt = acos_be
    
    return (
        float(r_net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        float(acos_be.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        float(acos_opt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    )


def calculate_book_economics(
    pages: int,
    marketplace: str,
    price: float,
    ink_type: str = "black",
    width_inches: Optional[float] = None,
    height_inches: Optional[float] = None,
    royalty_rate: float = 0.6,
) -> Optional[dict]:
    result = calculate_printing_cost(
        pages=pages,
        marketplace=marketplace,
        ink_type=ink_type,
        width_inches=width_inches,
        height_inches=height_inches,
    )
    
    if result is None:
        return None
    
    c_print, currency = result
    
    r_net, acos_be, acos_opt = calculate_acos_values(
        price=price,
        c_print=float(c_print),
        royalty_rate=royalty_rate,
        k=float(ACOS_RATIO),
    )
    
    return {
        "c_print": float(c_print),
        "currency": currency,
        "r_net": r_net,
        "acos_be": acos_be,
        "acos_opt": acos_opt,
        "trim_size": get_trim_category(width_inches, height_inches),
    }
