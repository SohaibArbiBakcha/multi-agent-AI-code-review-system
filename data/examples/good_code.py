"""A small, well-behaved module used as the "good" reference sample."""


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a Celsius temperature to Fahrenheit."""
    return celsius * 9 / 5 + 32


def average(values: list[float]) -> float:
    """Return the arithmetic mean of a non-empty list of numbers."""
    if not values:
        raise ValueError("values must not be empty")
    return sum(values) / len(values)


def is_palindrome(text: str) -> bool:
    """Return True if text reads the same forwards and backwards."""
    normalized = text.lower().replace(" ", "")
    return normalized == normalized[::-1]
